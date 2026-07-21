# SMF80 PassTicket Implementation

`PassTicketService.generate()` now emits structured Type 80 PassTicket generation evidence with event code 82.

`PassTicketService.validate()` now emits structured Type 80 PassTicket evaluation evidence with event code 81 for success and failure cases including not found, expired, user mismatch, APPL mismatch, replay and APPL authorization failures.
