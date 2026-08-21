# Integration boundary

This package contains adapters for external collaboration and infrastructure services,
such as Feishu, email, SMS, and object storage, when a real integration is introduced.

Integrations may call explicit Backend services and contracts. They do not own business
entities, replace PostgreSQL, or allow Workers to use an external spreadsheet as the
system of record. No provider implementation is created until a real contract exists.
