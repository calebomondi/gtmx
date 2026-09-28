# Make user-facing copy product/service-agnostic (copy-only)

## Goal
Copy at `/new` (and everywhere else) must not imply workspaces are product-only. Wording style: **"product/service"** (matches the existing `Product/Service` tab). Established domain terms (**product-market fit**, **Product Domain Understanding**, result-section headers) stay unchanged. **Copy only** — no renames of identifiers, routes, backend fields, interrupt types, or tab values.

## Edits

### 1. `frontend/src/components/new-workspace-form.tsx` (primary — /new)
| Line | Before | After |
|---|---|---|
| 332 | `Create a product workspace` | `Create a product/service workspace` |
| 334 | `...dedicated to the product you provide information for.` | `...dedicated to the product or service you provide information for.` |
| 340 | `Product name *` | `Product/service name *` |
| 342 | `Helps me know which product to focus on.` | `Helps me know which product or service to focus on.` |
| 347 | placeholder `ProductX` | placeholder `e.g. Acme` |
| 357 | `The product's page` | `The product/service page` |
| 46 (`SelectProduct`) | `... Products I found mentioned there:` | `... Here's what I found mentioned there:` |
| 117 | `Edit product description` | `Edit product/service description` |
| 456–457 | fallback `"your product"` (×2) | `"your product/service"` |

### 2. `frontend/src/product/product-components.tsx`
| Line | Before | After |
|---|---|---|
| ~200 (`EmptyProduct` heading) | `No product profile yet for {name}` | `No product/service profile yet for {name}` |
| ~203 | `...capture the product snapshot, domain and market-fit...` | `...capture the product/service snapshot, domain and market-fit...` |
| 412 | dialog title `Edit product snapshot` | `Edit product/service snapshot` |
| 414 | `...about the product so far.` | `...about the product/service so far.` |
| 423 | placeholder `Product name` (snapshot name input) | `e.g. Acme` |
| 884 | label `Product name` (ICP dialog) | `Product/service name` |
| 888 | placeholder `Product name` (ICP dialog) | `e.g. Acme` |
| 1100 | fallback `?? 'your product'` | `?? 'your product/service'` |
| 1391 | `How the product fits into its domain/category...` | `How the product/service fits into its domain/category...` |
| 1404 | `How well the product fits its market...` | `How well the product/service fits its market...` |

Already agnostic (no change): `Product/Service` tab heading (1118), `Product/Service snapshot` (1155), `How the agent summarises the product/service` (1137).

### 3. `frontend/src/components/workspace-manager.tsx` (~160)
`...the product name the agent found stays as-is.` → `...the product/service name the agent found stays as-is.`

### 4. `frontend/src/agent-chat/agent-chat.tsx` (13)
`Your conversational product & GTM analyst.` → `Your conversational product/service & GTM analyst.`

### 5. `frontend/src/feed/feed-components.tsx` (411)
fallback `?? 'your product'` → `?? 'your product/service'`

### 6. `frontend/src/sidepanel/workspace.tsx` (stepper, ~50)
`Understanding your product domain and its positioning` → `Understanding your product/service domain and its positioning`
Keep `Defining your product-market fit` (term of art).

## Explicitly unchanged
- Tab `Product/Service` (already agnostic); tab value `'product'`; all identifiers (`product_name`, `product_url`, interrupts, DTOs, backend)
- `Product Domain Understanding` / `Product-Market Fit Understanding` headers in `chain_of_thought/display.tsx`
- `chain_of_thought/thought.tsx` step title `Understanding your product domain` (matches kept headers)
- `ChooseOfferType` screen (`Is "..." a PRODUCT or a SERVICE?` — already agnostic)
- home-feed signal-category chip `Product` (signal category, not workspace type)
- Empty-state copy in home-feed / feed / competition (no product-only implication)

## Verification
1. `npx tsc -p tsconfig.app.json --noEmit` → 0
2. `npm run lint` → 0 errors
3. `npx vite build` → 0
4. `rg -n "product workspace|which product to focus|The product's page|your product'"` over `src/` → only intended (kept) hits
