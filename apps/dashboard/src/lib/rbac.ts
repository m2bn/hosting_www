export type Role = "owner" | "admin" | "developer" | "billing" | "viewer";

export type Permission =
  | "organization:view"
  | "organization:update"
  | "organization:delete"
  | "members:manage"
  | "projects:view"
  | "projects:create"
  | "projects:update"
  | "projects:deploy"
  | "domains:manage"
  | "billing:manage";

export type AccessContext = {
  role?: Role;
  permissions?: Permission[];
};

const rolePermissions: Record<Role, Permission[]> = {
  owner: [
    "organization:view",
    "organization:update",
    "organization:delete",
    "members:manage",
    "projects:view",
    "projects:create",
    "projects:update",
    "projects:deploy",
    "domains:manage",
    "billing:manage",
  ],
  admin: ["organization:view", "organization:update", "members:manage", "projects:view", "projects:create", "projects:update", "projects:deploy", "domains:manage"],
  developer: ["organization:view", "projects:view", "projects:create", "projects:update", "projects:deploy"],
  billing: ["organization:view", "projects:view", "billing:manage"],
  viewer: ["organization:view", "projects:view"],
};

export function permissionsForRole(role?: Role): Permission[] {
  return role ? rolePermissions[role] : [];
}

export function canAccess(context: AccessContext | undefined, permission: Permission): boolean {
  if (!context) {
    return false;
  }
  return new Set([...(context.permissions ?? []), ...permissionsForRole(context.role)]).has(permission);
}

export function canAny(context: AccessContext | undefined, permissions: Permission[]): boolean {
  return permissions.some((permission) => canAccess(context, permission));
}
