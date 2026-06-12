from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from apps.api import audit_log
from apps.api.entitlements import get_storage_limit, get_transfer_limit
from apps.api.models import SecurityEvent, SecuritySeverity, UsageMetric, UsageRecord


GB = Decimal(1024**3)
THRESHOLDS = (Decimal("0.8"), Decimal("0.9"), Decimal("1.0"))


@dataclass(frozen=True)
class UsageSample:
    organization: object
    project: object
    metric: str
    quantity: Decimal
    measured_at: object
    environment: object | None = None
    domain: object | None = None
    source: str = "metering"


def aggregate_hourly(samples):
    return _aggregate_samples(samples, granularity="hour")


def aggregate_daily(day=None):
    day = day or timezone.now().date()
    start = timezone.datetime.combine(day, timezone.datetime.min.time(), tzinfo=timezone.get_current_timezone())
    end = start + timedelta(days=1)
    groups = {}
    records = UsageRecord.objects.filter(period_start__gte=start, period_end__lte=end, source__startswith="metering:hourly")
    for record in records.select_related("organization", "project", "environment"):
        key = (record.organization_id, record.project_id, record.environment_id, record.metric, _daily_source(record.source))
        groups.setdefault(key, {"record": record, "quantity": Decimal(0)})
        groups[key]["quantity"] += record.quantity
    created = []
    for group in groups.values():
        base = group["record"]
        created.append(
            UsageRecord.objects.create(
                organization=base.organization,
                project=base.project,
                environment=base.environment,
                metric=base.metric,
                quantity=group["quantity"],
                unit=base.unit,
                period_start=start,
                period_end=end,
                source=group["record"].source.replace("metering:hourly", "metering:daily", 1),
            )
        )
    return created


def record_storage_usage(*, organization, project, bytes_used, measured_at=None, environment=None):
    measured_at = measured_at or timezone.now()
    quantity = Decimal(bytes_used) / GB
    return aggregate_hourly(
        [
            UsageSample(
                organization=organization,
                project=project,
                environment=environment,
                metric=UsageMetric.STORAGE_GB_HOURS,
                quantity=quantity,
                measured_at=measured_at,
                source="storage",
            )
        ]
    )


def record_transfer_usage(*, organization, project, domain=None, bytes_egressed=0, measured_at=None, environment=None):
    measured_at = measured_at or timezone.now()
    return aggregate_hourly(
        [
            UsageSample(
                organization=organization,
                project=project,
                environment=environment,
                domain=domain,
                metric=UsageMetric.EGRESS_BYTES,
                quantity=Decimal(bytes_egressed),
                measured_at=measured_at,
                source="transfer",
            )
        ]
    )


def record_runtime_usage(*, organization, project, cpu_seconds, memory_gb_hours, measured_at=None, environment=None):
    measured_at = measured_at or timezone.now()
    return aggregate_hourly(
        [
            UsageSample(
                organization=organization,
                project=project,
                environment=environment,
                metric=UsageMetric.CPU_SECONDS,
                quantity=Decimal(cpu_seconds),
                measured_at=measured_at,
                source="runtime",
            ),
            UsageSample(
                organization=organization,
                project=project,
                environment=environment,
                metric=UsageMetric.MEMORY_GB_HOURS,
                quantity=Decimal(memory_gb_hours),
                measured_at=measured_at,
                source="runtime",
            ),
        ]
    )


def evaluate_usage_thresholds(organization):
    alerts = []
    alerts.extend(_evaluate_metric(organization, UsageMetric.STORAGE_GB_HOURS, get_storage_limit(organization), divisor=Decimal(1), unit="gb"))
    alerts.extend(_evaluate_metric(organization, UsageMetric.EGRESS_BYTES, get_transfer_limit(organization), divisor=GB, unit="gb"))
    return alerts


def usage_exceeds_hard_limit(organization):
    return any(alert["threshold"] == Decimal("1.0") for alert in evaluate_usage_thresholds(organization))


def prometheus_metrics(organization=None):
    queryset = UsageRecord.objects.all()
    if organization is not None:
        queryset = queryset.filter(organization=organization)
    rows = (
        queryset.values("organization__public_id", "project__public_id", "metric")
        .annotate(total=Sum("quantity"))
        .order_by("metric")
    )
    lines = [
        "# HELP platform_usage_quantity Aggregated platform usage quantity.",
        "# TYPE platform_usage_quantity gauge",
    ]
    for row in rows:
        org_id = row["organization__public_id"]
        project_id = row["project__public_id"] or ""
        metric = row["metric"]
        lines.append(f'platform_usage_quantity{{organization="{org_id}",project="{project_id}",metric="{metric}"}} {row["total"]}')
    return "\n".join(lines) + "\n"


def usage_summary(organization):
    records = UsageRecord.objects.filter(organization=organization).values("metric").annotate(total=Sum("quantity")).order_by("metric")
    limits = {
        UsageMetric.STORAGE_GB_HOURS: get_storage_limit(organization),
        UsageMetric.EGRESS_BYTES: get_transfer_limit(organization),
    }
    return [
        {
            "metric": row["metric"],
            "quantity": str(row["total"]),
            "limit": limits.get(row["metric"]),
        }
        for row in records
    ]


def _aggregate_samples(samples, granularity):
    grouped = {}
    for sample in samples:
        if sample.organization is None or sample.project is None:
            raise ValueError("Usage samples must include organization and project.")
        period_start = _truncate(sample.measured_at, granularity)
        period_end = period_start + (timedelta(hours=1) if granularity == "hour" else timedelta(days=1))
        source = _source(sample, granularity)
        key = (
            sample.organization.id,
            sample.project.id,
            getattr(sample.environment, "id", None),
            sample.metric,
            source,
            period_start,
            period_end,
        )
        grouped.setdefault(key, {"sample": sample, "quantity": Decimal(0), "source": source, "period_start": period_start, "period_end": period_end})
        grouped[key]["quantity"] += sample.quantity
    records = []
    for group in grouped.values():
        sample = group["sample"]
        records.append(
            UsageRecord.objects.create(
                organization=sample.organization,
                project=sample.project,
                environment=sample.environment,
                metric=sample.metric,
                quantity=group["quantity"],
                unit=_unit(sample.metric),
                period_start=group["period_start"],
                period_end=group["period_end"],
                source=group["source"],
            )
        )
    for record in records:
        evaluate_usage_thresholds(record.organization)
    return records


def _evaluate_metric(organization, metric, limit, divisor, unit):
    if limit is None:
        return []
    total = UsageRecord.objects.filter(organization=organization, metric=metric).aggregate(total=Sum("quantity"))["total"] or Decimal(0)
    normalized = Decimal(total) / divisor
    alerts = []
    for threshold in THRESHOLDS:
        if normalized >= Decimal(limit) * threshold:
            event_type = f"usage.{metric}.{int(threshold * 100)}"
            event, created = SecurityEvent.objects.get_or_create(
                organization=organization,
                category="usage",
                event_type=event_type,
                source="metering-service",
                correlation_id=f"{organization.public_id}:{event_type}",
                defaults={
                    "severity": SecuritySeverity.HIGH if threshold >= Decimal("0.9") else SecuritySeverity.MEDIUM,
                    "metadata": {"metric": metric, "usage": str(normalized), "limit": limit, "unit": unit, "threshold": str(threshold)},
                },
            )
            if created:
                audit_log.record(
                    action=audit_log.AuditAction.USAGE_LIMIT_EXCEEDED if threshold == Decimal("1.0") else audit_log.AuditAction.USAGE_LIMIT_THRESHOLD_REACHED,
                    organization=organization,
                    target_type="usage",
                    target_id=f"{metric}:{int(threshold * 100)}",
                    metadata={"metric": metric, "usage": str(normalized), "limit": limit, "unit": unit, "threshold": str(threshold)},
                )
            alerts.append({"event": event, "threshold": threshold, "metric": metric})
    return alerts


def _truncate(value, granularity):
    if granularity == "day":
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return value.replace(minute=0, second=0, microsecond=0)


def _source(sample, granularity):
    prefix = f"metering:{granularity}ly"
    if sample.domain is not None:
        return f"{prefix}:{sample.source}:domain:{sample.domain.public_id}"[:100]
    return f"{prefix}:{sample.source}"[:100]


def _daily_source(source):
    return source.split(":domain:", 1)[0] if ":domain:" in source else source


def _unit(metric):
    return {
        UsageMetric.STORAGE_GB_HOURS: "gb_hours",
        UsageMetric.EGRESS_BYTES: "bytes",
        UsageMetric.CPU_SECONDS: "seconds",
        UsageMetric.MEMORY_GB_HOURS: "gb_hours",
        UsageMetric.BUILD_MINUTES: "minutes",
    }.get(metric, "units")
