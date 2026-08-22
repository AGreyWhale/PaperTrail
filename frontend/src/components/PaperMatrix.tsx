import { Link } from "react-router-dom";

export interface MatrixColumn {
  paper_id: string;
  title: string;
}

export interface MatrixRow {
  label: string;
  //Keyed by paper_id, so column order drives the cells
  cells: Record<string, string>;
}

interface PaperMatrixProps {
  rowHeader: string;
  columns: MatrixColumn[];
  rows: MatrixRow[];
}

//Rows-by-papers grid, shared by the compare table and the review's themes
//table — same shape, so one implementation rather than two that drift
export function PaperMatrix({ rowHeader, columns, rows }: PaperMatrixProps) {
  return (
    // Wide tables scroll inside their own container rather than pushing the
    // page sideways.
    <div className="overflow-x-auto border border-border rounded-card bg-surface">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            <th className="text-left font-sans text-xs uppercase tracking-wide text-text-muted px-4 py-3 border-b border-border w-40 align-bottom">
              {rowHeader}
            </th>
            {columns.map((column) => (
              <th
                key={column.paper_id}
                className="text-left px-4 py-3 border-b border-border align-bottom min-w-56"
              >
                <Link
                  to={`/papers/${column.paper_id}`}
                  className="font-serif text-base text-text-primary hover:text-accent-primary transition-colors"
                >
                  {column.title}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="align-top">
              <th className="text-left font-sans font-medium text-text-secondary px-4 py-3 border-b border-border bg-bg-secondary/40">
                {row.label}
              </th>
              {columns.map((column) => (
                <td
                  key={column.paper_id}
                  className="px-4 py-3 border-b border-border text-text-primary leading-relaxed"
                >
                  {row.cells[column.paper_id] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
