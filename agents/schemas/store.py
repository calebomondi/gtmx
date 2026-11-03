"""A Lace's Store: the digital products and services it sells on its own,
within rules only people set. The money sits in a NEAR Intents Agent API
wallet whose policy the founder signs."""

from typing import Literal

# setup: being configured, nothing on sale. live: selling. paused: the team
# stopped new checkouts on our side; the wallet's own freeze is separate.
StoreStatus = Literal["setup", "live", "paused"]
STORE_STATUSES: tuple[str, ...] = StoreStatus.__args__

# How a paid order is fulfilled: a private link (a download, a course, an
# invite) emailed to the buyer, or a service the team delivers once told.
OfferDelivery = Literal["link", "service"]
OFFER_DELIVERIES: tuple[str, ...] = OfferDelivery.__args__
# draft: written (by a person or drafted by the Lace) and not yet on sale.
OfferStatus = Literal["draft", "active", "archived"]
OFFER_STATUSES: tuple[str, ...] = OfferStatus.__args__

# Where a payee's share goes: another NEAR Intents account (transfer), or
# out to an address on a chain (withdraw). Both must be in the signed policy.
PayeeRoute = Literal["transfer", "withdraw"]
PAYEE_ROUTES: tuple[str, ...] = PayeeRoute.__args__

OrderStatus = Literal["awaiting_payment", "paid", "delivered", "refunded", "failed", "expired"]
ORDER_STATUSES: tuple[str, ...] = OrderStatus.__args__

# The public ledger. sale: a payment credited. payout: a share sent to a payee.
# refund: a payment returned. cost: what the Store's own running spent.
LedgerKind = Literal["sale", "payout", "refund", "cost"]
LEDGER_KINDS: tuple[str, ...] = LedgerKind.__args__
LedgerStatus = Literal["pending", "done", "failed"]
LEDGER_STATUSES: tuple[str, ...] = LedgerStatus.__args__

# What the founder's wallet signs for a Store, through the Agent API.
StoreIntentType = Literal["agent_create", "grant_issue", "policy_update", "agent_freeze", "agent_unfreeze"]
STORE_INTENT_TYPES: tuple[str, ...] = StoreIntentType.__args__
StoreIntentStatus = Literal["awaiting_signature", "submitted", "succeeded", "failed", "expired"]
STORE_INTENT_STATUSES: tuple[str, ...] = StoreIntentStatus.__args__

# Basis points: a payee's share of each sale. What no payee takes stays in the
# Store's wallet, its operating balance.
FULL_SHARE_BPS = 10_000
STORE_SLUG_PATTERN = "^[a-z0-9](?:[a-z0-9-]{1,46}[a-z0-9])$"
STORE_SLUG_MAX_LEN = 48
