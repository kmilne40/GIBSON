# CTI Authentication Implementation

CTI admin actions can be protected by Basic Auth. Relevant settings:

- `GIBSON_CTI_AUTH_ENABLED=1`
- `GIBSON_CTI_USER=ctiadmin`
- `GIBSON_CTI_PASSWORD=gibson`
- `GIBSON_CTI_USE_DASHBOARD_AUTH=1` to reuse dashboard credentials
- `GIBSON_CTI_READONLY_PUBLIC=0` to protect all CTI pages

Read-only pages remain public by default unless configured otherwise.
