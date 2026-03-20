# CLEAR CUID PROCEDURE DOCUMENT — POC VERSION

## PHONE ERROR PROCEDURES

### CUID-PH-001: International to Domestic Phone Conversion

Category: Phone — Severity: Medium

This error occurs when a customer's record contains an international phone number (stored in the `homePhoneNbr` field with an international prefix like "+44..." or "+82...") and the banker is trying to replace it with a US domestic number. The system rejects the update because of a format validation mismatch between the existing international format and the new domestic format.

Error messages the banker may see on screen: "INVALID PHONE FORMAT - COUNTRY CODE MISMATCH", "PH-ERR-101: CANNOT UPDATE - INTERNATIONAL FORMAT DETECTED", or "PHONE UPDATE FAILED: FORMAT VALIDATION ERROR".

How the banker may describe it: "Customer has an international phone number and wants to change to a domestic number", "System won't accept the new US number because the old one is international", or "Getting a format error when trying to change the phone number."

Diagnostic questions to confirm this error: Is the customer's current phone number an international number (non-US country code)? Are you trying to replace it with a US domestic number? What is the exact error message you're seeing on screen?

Preconditions before taking action: The banker must have noted the customer's new domestic phone number. The banker must have verified the customer's identity.

Remediation: Clear the `homePhoneNbr` field by sending a PATCH to `/customers/{inputKey}` with `homePhoneNbr` set to an empty string. If the international number is in the `businessPhoneNbr` field instead, clear that field. The agent must first GET the customer profile to retrieve the required PATCH fields: `companyNbr`, `customerTie`, `customerNameLine1`, `birthDt`, `genderCd`, `customerOfficer1Cd`, `customerOfficer2Cd`, `sensitivityCode`.

Post-action instructions for the banker: "After I clear the data, please re-enter the customer's new domestic phone number. The system should now accept it without the country code format mismatch."

Escalate to a live agent if: The customer has multiple international phone numbers across both `homePhoneNbr` and `businessPhoneNbr`, or the phone field still returns the old value after the PATCH.

---

### CUID-PH-002: Duplicate Phone Number

Category: Phone — Severity: Medium

This error occurs when the phone number the banker is trying to enter is already assigned to another customer record in the system. The `homePhoneNbr` value exists on another CIF, and Hogan blocks the update to prevent duplicate phone associations.

Error messages the banker may see on screen: "DUPLICATE PHONE - RECORD ALREADY EXISTS", "PH-ERR-201: PHONE NUMBER LINKED TO ANOTHER CIF", or "CANNOT ADD: PHONE NUMBER IN USE BY ANOTHER CUSTOMER".

How the banker may describe it: "The phone number is already assigned to another customer", "Getting a duplicate phone error", or "System says this number is already in the system under someone else."

Diagnostic questions to confirm this error: Is the phone number you're trying to enter already associated with another customer in the system? Can you confirm the phone number the customer wants to use?

Preconditions before taking action: The banker has confirmed the phone number belongs to this customer. The banker has verified the customer's identity.

Remediation: Clear the `homePhoneNbr` field by sending a PATCH to `/customers/{inputKey}` with `homePhoneNbr` set to an empty string. This releases the duplicate link so the banker can re-enter the number. The agent must first GET the customer profile to retrieve the required PATCH fields.

Post-action instructions for the banker: "The phone field should now be editable. Please try entering the phone number again. If the duplicate error persists, the other customer's record may need to be updated first — in that case, I'll need to connect you with a specialist."

Escalate to a live agent if: The other customer's `homePhoneNbr` also contains the same value (both records need clearing), or the phone is linked to more than 2 customer records.

---

### CUID-PH-003: Corrupted ECN Phone Link

Category: Phone — Severity: High

This error occurs when the linkage between the customer record (ECN) and the phone data is corrupted, typically after a record migration or merge. The banker cannot edit, add, or remove any phone data because the system detects a data integrity issue.

Error messages the banker may see on screen: "ECN PHONE LINK INVALID - DATA INTEGRITY ERROR", "PH-ERR-301: CUSTOMER-PHONE RELATIONSHIP CORRUPTED", or "CANNOT MODIFY: ECN PHONE POINTER MISMATCH".

How the banker may describe it: "Can't edit the phone number at all, system gives a data integrity error", "The phone entry seems corrupted or broken", or "ECN error when trying to do anything with the phone number."

Diagnostic questions to confirm this error: When you try to access the phone field, does the system show a data integrity or ECN error? Has this customer's record been recently migrated or merged?

Preconditions before taking action: The banker must have noted all current phone numbers on the account. The banker must have verified the customer's identity.

Remediation: Clear ALL phone fields by sending a PATCH to `/customers/{inputKey}` with both `homePhoneNbr` and `businessPhoneNbr` set to empty strings. For business customers with `commercialContactInfo` entries, also send `contactActionCd: "D"` (delete) for each contact entry. The agent must first GET the customer profile to retrieve the required PATCH fields.

Post-action instructions for the banker: "All phone entries have been cleared. Please re-enter each phone number for the customer. Start with the primary home phone number."

Escalate to a live agent if: The customer record itself appears to be corrupted (not just phone fields), or phone fields still return old values after the PATCH.

---

## ID ERROR PROCEDURES

### CUID-ID-001: Primary ID Update Blocked

Category: ID — Severity: Medium

This error occurs when the customer's primary identification document fields (`documentType`, `documentNbr`, `documentIssueDt`, `documentIssuePlace`) are in a hold/locked state, preventing the banker from updating them. This typically happens when a verification process was initiated but not completed, or when the system placed an automatic hold.

Error messages the banker may see on screen: "ID UPDATE BLOCKED - VERIFICATION PENDING", "ID-ERR-101: PRIMARY ID LOCKED FOR MODIFICATION", or "CANNOT MODIFY PRIMARY IDENTIFICATION - HOLD STATUS".

How the banker may describe it: "Can't update the customer's driver's license, it's locked", "Primary ID won't let me make changes, says verification pending", or "Customer renewed their ID but I can't update the new one in the system."

Diagnostic questions to confirm this error: Are you trying to update the customer's primary identification document? What type of ID is it (driver's license, passport, state ID)? Does the system show a "pending verification" or "hold" status on the ID?

Preconditions before taking action: The banker has the new ID document in hand and has verified it. The banker has noted the new ID number and expiration date.

Remediation: Clear the document fields by sending a PATCH to `/customers/{inputKey}` with `documentType`, `documentNbr`, `documentIssueDt`, and `documentIssuePlace` all set to empty strings. This releases the hold so the banker can enter the new ID details. The agent must first GET the customer profile to retrieve the required PATCH fields.

Post-action instructions for the banker: "The ID fields should now be editable. Please update the identification with the new document type, number, issuing state/country, and expiration date."

Escalate to a live agent if: The ID is locked due to a fraud investigation hold, or the document fields still show the old values after the PATCH.

---

### CUID-ID-002: Document Type Mismatch on ID Replace

Category: ID — Severity: Low

This error occurs when the banker is trying to replace the customer's primary identification document with a different document type (e.g., replacing a passport with a driver's license), but the system rejects the update because the existing `documentType` value conflicts with the new type, or the existing ID has not yet expired. Hogan blocks the overwrite to prevent accidental loss of valid identification data.

Error messages the banker may see on screen: "ID TYPE MISMATCH - CANNOT OVERWRITE", "ID-ERR-201: DOCUMENT TYPE CONFLICT ON UPDATE", or "UPDATE FAILED: EXISTING ID TYPE DIFFERS FROM NEW ENTRY".

How the banker may describe it: "I'm trying to change the ID type but it won't let me overwrite it", "System says there's a type mismatch when I try to update the ID", or "Can't replace the passport with a driver's license, getting a conflict error."

Diagnostic questions to confirm this error: Are you trying to replace the customer's current ID with a different type of document? What is the current ID type on file, and what type are you trying to enter? Is the current ID still within its valid/unexpired date range?

Preconditions before taking action: The banker has the new ID document in hand and has verified it. The banker has confirmed the customer wants the existing ID replaced (not kept alongside the new one).

Remediation: Clear the document fields by sending a PATCH to `/customers/{inputKey}` with `documentType`, `documentNbr`, `documentIssueDt`, and `documentIssuePlace` all set to empty strings. This removes the conflicting type so the banker can enter the new ID. The agent must first GET the customer profile to retrieve the required PATCH fields: `companyNbr`, `customerTie`, `customerNameLine1`, `birthDt`, `genderCd`, `customerOfficer1Cd`, `customerOfficer2Cd`, `sensitivityCode`.

Post-action instructions for the banker: "The existing ID has been cleared. Please enter the new identification document with the correct type, number, issuing state/country, and expiration date."

Escalate to a live agent if: The customer's existing primary ID must remain on record for compliance or audit reasons while also needing the new ID on file, or the existing ID is linked to an active fraud or regulatory review.

---

## COMBINED PHONE + ID ERRORS

When a banker reports both phone and ID issues on the same customer, the agent handles them sequentially: resolve the phone issue first (using the appropriate CUID-PH procedure above), then resolve the ID issue (using the appropriate CUID-ID procedure above), then verify both are resolved before closing the conversation.
