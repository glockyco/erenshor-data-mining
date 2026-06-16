// Minimal ambient declaration for the bun:sqlite surface this tool uses, so
// `tsc` typechecks under `types: ["node"]` without pulling in all of @types/bun.
// Bun provides the real implementation at runtime.
declare module "bun:sqlite" {
  export class Database {
    constructor(filename: string, options?: { readonly?: boolean });
    query<R = unknown>(sql: string): { all(): R[] };
    close(): void;
  }
}
