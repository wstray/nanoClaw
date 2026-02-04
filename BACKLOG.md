# BACKLOG

## Features

### Tailscale Serve: Auto-approve device pairing

When accessing webchat via Tailscale Serve with `gateway.auth.allowTailscale: true`, users must manually approve device pairing every time browser localStorage gets cleared. This creates a chicken-and-egg problem: need to approve from another session before using webchat.

Request: add config option to auto-approve device pairing when request comes from Tailscale Serve with valid identity headers. If user trusts Tailscale enough to skip token auth, they should be able to trust it for device pairing too.

Priority: Low (edge case for advanced self-hosted setups)
