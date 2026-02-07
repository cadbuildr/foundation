# ⚠️ DEPRECATED - Old Foundation Implementation

**This package is deprecated and kept only for reference and testing purposes.**

The old manual implementation in this directory has been replaced by a new schema-driven approach where Python types are automatically generated from the GraphQL schema located in `/schemas/foundation/`.

## What replaced this?

The new foundation package (`py/packages/cadbuildr/foundation/`) now uses:
- GraphQL schema as the single source of truth (`/schemas/foundation/schema.graphql`)
- Automatic code generation via `graphql-codegen` 
- Zero hardcoded types - everything is generated from the schema

## Why keep this?

This old implementation is kept temporarily to:
1. Provide examples and test cases
2. Ensure backward compatibility during migration
3. Serve as reference for the new implementation

## Migration

If you're using this package, please migrate to the new `cadbuildr.foundation` package which provides the same functionality with a cleaner, schema-driven approach.

---

**Do not add new features or make significant changes to this deprecated package.**
