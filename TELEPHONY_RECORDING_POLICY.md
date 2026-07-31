# Call Recording Scope Policy (locked, effective v1.0 Telephony design)

This CRM's call-recording feature fetches recordings only for calls matching
a phone number that exists as a lead or client in the CRM database. No
recording is ever scanned, read, or uploaded for any number that is not an
existing CRM lead/client — including personal calls, family, friends, or any
number not present in the system. Matching happens server-side against the
CRM's own lead records, not by scanning a phone's entire recording history.
This is a binding company rule, not a technical limitation. Employees should
have zero concern about personal call privacy under this feature.

## DPDP Act note

This document covers the scope/privacy *design* of the call-recording
feature — it does not cover consent-notice mechanics. Call recording under
India's DPDP Act still requires appropriate consent notices to be in place
before this feature goes live for real use. That remains a separate, still
open item and must be resolved before Phase B moves past pilot/testing.
