"""Describes the CoLunch domain. Centres around the `RecipeBook`.

Why is this hard?

- The process of creating a recipe is closely tied to large language models.
  These tend to be served behind apis.
- The process of search is closely tied to embeddings.
- No invariants that need to be enforced.
- Largely because creation is handled by the machine and modification is not
  allowed.

Should be able to fake those.

But that still leaves you mixing the layers of the onion.
There will be external services in the domain.

Does anyone care?
"""
