# intData-tools Connectors

`connectors/` contains public reusable connector tooling salvaged from the
retired `intNexus` product contour.

## Packages

- `sdk/` - `@inttools/connector-sdk`, base lifecycle, event, metadata, error,
  and context types for CRM/LMS/SaaS connectors.
- `examples/` - `@inttools/connector-examples`, cookbook implementations for
  Bitrix24, amoCRM, and GetCourse.

## Boundary

These packages are reusable tooling and examples, not a production integration
runtime. Product backends own their runtime wiring, secrets, queues, storage,
and deployment.

## Security

- Do not commit real tokens, API keys, client secrets, refresh tokens, webhook
  secrets, or runtime `.env` files.
- Keep examples deterministic and safe for public review.
- Use environment variables or product-owned secret storage when adapting these
  examples into a real service.

## Validation

```bash
npm install --prefix /int/tools/connectors/sdk
npm run build --prefix /int/tools/connectors/sdk
npm install --prefix /int/tools/connectors/examples
npm test --prefix /int/tools/connectors/examples
```
