import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";

const projects = [
  { name: "Marketing Site", org: "Acme", status: "active", deploy: "7 minutes ago", usage: "12 GB" },
  { name: "Customer Portal", org: "Acme", status: "active", deploy: "1 hour ago", usage: "38 GB" },
  { name: "Docs", org: "Northwind", status: "pending", deploy: "Queued", usage: "4 GB" },
];

export function ProjectTable() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent projects</CardTitle>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <Table>
          <TableHead>
            <tr>
              <Th>Name</Th>
              <Th>Organization</Th>
              <Th>Status</Th>
              <Th>Last deployment</Th>
              <Th>Storage</Th>
            </tr>
          </TableHead>
          <TableBody>
            {projects.map((project) => (
              <tr key={project.name}>
                <Td className="font-semibold">{project.name}</Td>
                <Td>{project.org}</Td>
                <Td>
                  <Badge variant={project.status === "active" ? "success" : "warning"}>{project.status}</Badge>
                </Td>
                <Td>{project.deploy}</Td>
                <Td>{project.usage}</Td>
              </tr>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
