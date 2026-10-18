# Issue 1.1 — establish the `product` package boundary

**Status: Not started**

Create the neutral target import root for new code. This is a parallel target
boundary, not a repository-wide rename; the old application remains runnable
until Wave 5 cutover.

## Tasks

- [Task 1.1.1 — add the target package root](task-1.1.1-add-product-package-root.md)

## Dependencies

- [Wave 0 census](../../wave-0-census/README.md)
- [Architecture documentation](../../../../architecture/README.md)

## Communication DTOs

None introduced by this issue. Package paths define ownership, not a runtime
message contract.
