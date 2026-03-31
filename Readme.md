# CADbuildr Foundation

## Summary

Schema-driven Python types for CAD modeling, generated from the GraphQL foundation schema.

## Tags

cad, python, foundation, schema

## Status

green

## Guidelines

- Keep generated code deterministic and reproducible across machines.
- Avoid manual edits in generated modules; change the schema instead.
- Keep public APIs stable and document migrations when needed.

## Dependencies

### Upstream

- (none)

### Downstream

All the CAD projects

## Notes

See `/schemas/foundation/` for schema definition.

## Kernel API Contract

- Canonical render endpoint: `POST /v1/kernels/:kernel/render` with `format=json|stl|step`.
- Foundation direct compile endpoint env: `CAD_COMPILE_API_BASE_URL`.
