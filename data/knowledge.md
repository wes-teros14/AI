## Knowledge Base Index

Category: Integration Architecture
- Connectivity Term Synonyms — API Endpoint URL Address
- Integration Classification — Standard vs Custom SAP Integration
- Integration Design — Record-Level Delta vs Field-Level Delta
- Integration Design Workshop — Common Questions to Ask Before Building

Category: SAP Integration Suite and CPI
- SAP Integration Suite — Tenant Provisioning and Licensing Reference
- ATO STP Integration — Multiple ABN Cross Entity Authorization

Category: BIB Replication
- BIB Replication — Replication Target System Configuration in SuccessFactors and S/4
- BIB Replication — What It Is and How It Works
- BIB Replication — Action Reason and BP Sync Behaviour
- BIB Replication — Employee Multiple Assignments Address Replication Failure and BP Sync Fix
- BIB Replication Failure — Data Not Arriving at S4 or ECC
- SAP Cloud Connector — Always Use Path and All Sub-paths
- SAPRouter — Purpose and When Required

Category: SuccessFactors OData API
- SuccessFactors Compound Employee API — Delta Behaviour and MDF Limitations
- SuccessFactors OData — Custom MDF Objects Cannot Navigate from PerPerson
- SuccessFactors OData — EmpPayCompRecurring Insert Behaviour and Delta Risk
- SuccessFactors OData — MDF Field API Visibility Rules

Category: SuccessFactors Configuration and Permissions
- SuccessFactors API User — Required Permissions for CPI Integration
- SuccessFactors Employee Central — Dropdown Values That Are Not Picklists
- SuccessFactors Employee Central — Foundation Object Upsert Requirements

Category: SuccessFactors Modules
- SuccessFactors Time Management — ExternalTimeData vs EmployeeTime and correctionScenario
- SuccessFactors LMS — Single Header Row File Configuration

Category: System Replication
- S4HANA to SuccessFactors — Cost Center Constraints and Code Concatenation
- SuccessFactors to ECP — Point-to-Point Connection Setup

---

# ════════════════════════════════════════════════════
# CATEGORY 1 — Integration Architecture
# ════════════════════════════════════════════════════

## Connectivity Term Synonyms — API, Endpoint, URL, Address

In SAP integration troubleshooting, the terms API, Endpoint, URL, and Address often refer to the same point of failure in an adapter configuration. API is the overarching authentication framework. Endpoint is the specific target object or function. URL is the absolute text string used to locate the system. Address is the network hostname. When a connection fails in CPI or any SAP adapter, verify all four before escalating.

---

## Integration Classification — Standard vs Custom SAP Integration

SAP integration content falls into two categories. Standard integrations are prepackaged Out-Of-The-Box content provided directly by SAP. They are usually read-only or restricted and modifications are only permitted via official extension points such as BAdI or IMG configuration. Troubleshooting standard integrations focuses on SAP Service Marketplace, Support Portal, and verifying the latest Content Version is deployed in CPI.

Custom integrations are built from scratch by the project team and are fully flexible and fully owned by the consultant. They include custom Groovy scripts, complex XSLT, and unique routing logic. Troubleshooting focuses on internal CPI message logs, trace mode, and debugging the specific mapping logic.

Decision rule: always check if standard content exists first to minimise maintenance. Only move to custom development if the requirement cannot be met via standard configuration or BAdI extensions.

---

## Integration Design — Record-Level Delta vs Field-Level Delta

When designing a SuccessFactors or SAP integration interface, the choice between Record-Level Delta and Field-Level Delta has the following trade-offs.

Record-Level Delta sends the full record whenever any field changes. It produces a larger payload and higher target system load since a full upsert runs each time, but is lower complexity and carries lower risk of data loss. Best for simple integrations and low volume. SuccessFactors OData supports this natively via $filter=lastModifiedDate.

Field-Level Delta sends only the changed fields. It produces a smaller payload and lower target system load, but requires custom change detection logic and carries a higher risk of missed field changes. Best for high-volume or bandwidth-sensitive scenarios.

---

## Integration Design Workshop — Common Questions to Ask Before Building

Before designing any SAP integration interface, ask these scoping questions.

Data scoping: Is this a full file load or delta only? Is it record-level or field-level delta? Do we send effective-dated records?

Handling changes: Do we send deleted records? Do we send records on the day they become effective or future-dated?

---

# ════════════════════════════════════════════════════
# CATEGORY 2 — SAP Integration Suite and CPI
# ════════════════════════════════════════════════════

## SAP Integration Suite — Tenant Provisioning and Licensing Reference

SAP Integration Suite is an umbrella platform that contains multiple services. Common services include SAP Integration Suite messaging and flows (the service most people refer to when they say CPI), Open Connectors, and API Management. Each service has its own subscription and licensing boundaries. Tenant provisioning details and subscription boundaries for SAP Integration Suite and its services are documented in SAP Note 2903776. Use this note to verify which services are included in a tenant subscription and to confirm provisioning status.

Reference: https://me.sap.com/notes/2903776

---

## ATO STP Integration — Multiple ABN Cross Entity Authorization

In the SAP CPI standard ATO/STP integration for Australia, when an organisation has multiple ABNs, one ABN acts as the Intermediate ABN (ABN A) representing others (ABN B, C) for STP reporting.

Setup: In the ATO portal, grant ABN A permission to represent ABN B. ABN A must accept the permission. This is called Cross Entity Authorization. Setup options: manual ATO form (slower) or RAM (Relationship Authorisation Manager) portal (self-service, faster).

Reference: https://drive.google.com/file/d/1-hM8c-mCcrbyvyIQnmp0NlBoW5UGjnT8/view?usp=drive_link

---

# ════════════════════════════════════════════════════
# CATEGORY 3 — BIB Replication
# ════════════════════════════════════════════════════

## BIB Replication — Replication Target System Configuration in SuccessFactors and S/4

In BIB replication, the Replication Target System must match between SuccessFactors and S/4.
In SuccessFactors, it is configured via Manage Data > Replication Target System. In S/4, it
is configured via TCode SM30, table V_ECPAO_QRY_CFG. Both sides must have the same code.

---
## BIB Replication — What It Is and How It Works

BIB (Business Integration Builder) is a replication framework developed by SAP that orchestrates the movement of employee and organisational data between SuccessFactors and S/4HANA or ECC. It is not a fully custom integration — it is a pre-built SAP framework with its own flow, mapping, and activation steps built into S/4 or ECC. Limited customisation is possible through custom field mappings and BAdI implementations within the BIB framework, but it does not support full custom development such as Z-programs.

The BIB replication flow works as follows.

Step 1: S/4 or ECC initiates the flow by sending a GET query to CPI to request data from SuccessFactors.
Step 2: CPI forwards the GET query to SuccessFactors on behalf of S/4 or ECC.
Step 3: SuccessFactors responds with the requested employee or organisational data back to CPI.
Step 4: CPI sends the data to S/4 or ECC. If S/4 or ECC is in a private or on-premise network, the data passes through the SAP Cloud Connector (SCC) before reaching the target system.
Step 5: Once received in S/4 or ECC, mapping and transformation of the SuccessFactors data is performed inside S/4 or ECC using the BIB framework mapping tools and any configured BAdI implementations.
Step 6: The transformed data is posted and saved into the S/4 or ECC system.

Key points: S/4 or ECC is the initiator of the BIB replication flow. CPI acts as the middleware broker. The mapping logic lives in S/4 or ECC within the BIB framework. BIB supports custom field mappings and BAdIs but not full custom development like Z-programs.

---

## BIB Replication — Action Reason and BP Sync Behaviour

In SuccessFactors to S/4HANA BIB replication, the Action Reason field in S/4 is not required in the replication mapping and can be omitted. When BIB pushes employee data to S/4 as HR Mini-Master, S/4 will subsequently create a Business Partner via the BP Sync job. This is an automatic downstream process in S/4, not triggered directly by BIB.

---


## BIB Replication — Employee Multiple Assignments Address Replication Failure and BP Sync Fix

When SuccessFactors is configured with Employee Multiple Assignments and both assignments
are active, address data sometimes does not replicate correctly to S/4 or ECC. This causes
the BP Sync job to fail because a valid address is required for Business Partner creation.
A possible fix is to check whether Home and Host address is enabled in SuccessFactors —
enabling it has resolved this issue in known cases.

References:
https://me.sap.com/notes/2917035
https://me.sap.com/notes/2347654
https://me.sap.com/notes/2835695

---

## BIB Replication Failure — Data Not Arriving at S/4 or ECC

When CPI is sending BIB replication data but S/4 or ECC is not receiving it, check these two common causes.

Fix 1 — SICF service inactive: TCode SICF > navigate to default_host/sap/bc/srt/scs/sap/. If greyed out, right-click > Activate Service. Inactive services silently reject inbound SOAP calls from CPI.

Fix 2 — SCC access policy wrong: SAP Cloud Connector > resource path for the S/4 system must be set to Path and All Sub-paths. If set to Exact Name, dynamic BIB calls will be silently blocked with no error message.

---

## SAP Cloud Connector — Always Use Path and All Sub-paths

In SAP Cloud Connector (SCC), when configuring resource paths for an on-premise system, always set the access policy to Path and All Sub-paths. Setting it to Exact Name silently blocks any integration using dynamic sub-paths — including BIB replication and CPI iFlows routing to dynamic resource paths. This is one of the most common silent failure modes in CPI-to-on-premise connectivity.

---

## SAPRouter — Purpose and When Required

SAPRouter is a proxy and relay component that must be installed on an S/4HANA or ECC on-premise system to allow SAPGUI access from an external network. Without SAPRouter on the on-premise system, SAPGUI cannot connect from outside the internal corporate network.

---

# ════════════════════════════════════════════════════
# CATEGORY 4 — SuccessFactors OData API
# ════════════════════════════════════════════════════

## SuccessFactors Compound Employee API — Delta Behaviour and MDF Limitations

In the SuccessFactors Compound Employee (CE) API, when using parameter=periodDelta, the pointer reference is the previous last modified date-time. A snapshot is taken on each query and this date-time is the key for change detection.

Regarding MDF objects in the CE API response: only custom MDF objects can be freely added. For standard MDF objects, only three are permitted: Work Order, Higher Duty Temp Assignment, and Onboarding Info.

Reference: https://help.sap.com/docs/successfactors-employee-central/employee-central-compound-employee-api/extending-api-with-mdf-objects?locale=en-US

---

## SuccessFactors OData — Custom MDF Objects Cannot Navigate from PerPerson

In SuccessFactors OData API, custom MDF objects cannot be navigated directly from the PerPerson entity. Because the navigation path from PerPerson does not exist for custom MDF objects, they cannot be used with Standard Delta synchronization. The workaround is to make a separate API call directly to the MDF entity, keyed by personIdExternal or userId.

---

## SuccessFactors OData — EmpPayCompRecurring Insert Behaviour and Delta Risk

In SuccessFactors OData API, the EmpPayCompRecurring entity behaves differently from standard entities. It groups all pay components under a single effective date, so every pay component on the same date shares that exact startDate. When a new pay component record is inserted, the system copies all existing active pay components to the new insertion date, refreshing the startDate for all components. This can cause unexpected delta triggers downstream in any integration monitoring pay component start dates.

---

## SuccessFactors OData — MDF Field API Visibility Rules

In SuccessFactors, visibility and API access for custom MDF objects are managed via Configure Object Definitions. For standard MDF objects, some fields have hardcoded visibility governed by Manage Business Configuration (BCUI) or Configure Employee Files — not only by RBP. Critical check: always verify the API Visibility attribute in the Object Definition. If set to Not Visible, the field will be excluded from OData metadata even if RBP permissions are fully granted.

---

# ════════════════════════════════════════════════════
# CATEGORY 5 — SuccessFactors Configuration and Permissions
# ════════════════════════════════════════════════════

## SuccessFactors API User — Required Permissions for CPI Integration

For an API user in SuccessFactors to support CPI or third-party integrations, the following permissions must be granted under Manage Permission Roles.

General User Permission: User Login, SFAPI User Login, Login Method (Password).
Employee Central API: EC Foundation SOAP API, EC HRIS SOAP API, EC Foundation OData API (Editable), EC HRIS OData API (Editable).
Manage Integration Tools: Allow admin to access OData API via Basic Authentication.
Manage User: User Account OData Entity.
Metadata Framework: Admin Access to MDF OData API.

---

## SuccessFactors Employee Central — Dropdown Values That Are Not Picklists

In SuccessFactors Employee Central, some dropdown lists such as National ID Card Type are not Picklists and will not appear in Picklist Center. These values are governed by the Country-Specific Data Model. To configure them, go to Manage Business Configuration > HRIS Elements > nationalIdCard > nationalIdCard_XXX where XXX is the country code. Always check here first if a dropdown value is missing from Picklist Center.

---

## SuccessFactors Employee Central — Foundation Object Upsert Requirements

When posting Foundation Object data from an external system to SuccessFactors Employee Central via API upsert or insert, the payload must include the defaultValue field and all required translations. Missing defaultValue or translations will cause the upsert to fail or create incomplete records in Employee Central.

---

# ════════════════════════════════════════════════════
# CATEGORY 6 — SuccessFactors Modules
# ════════════════════════════════════════════════════

## SuccessFactors Time Management — ExternalTimeData vs EmployeeTime and correctionScenario

In SuccessFactors Time Management integrations, clock-in/out from an external system is stored in OData entity ExternalTimeData. Clock-in/out from the SF UI is stored in EmployeeTime.

The correctionScenario field on ExternalTimeData controls editability. Default via TimeEvents API is EXTERNAL_SYSTEM (external system only). Setting it to TIME_SHEET_AND_EXTERNAL_SYSTEM allows editing from both SF Timesheet and the external system. If not set during POST, the record is editable from both by default.

Additional rules: Posting overtime to ExternalTimeData requires regular working time already recorded in SF for that period, otherwise the record errors. Posting overtime always triggers a workflow approval. A custom job can retroactively set correctionScenario = TIME_SHEET_AND_EXTERNAL_SYSTEM on existing records.

---

## SuccessFactors LMS — Single Header Row File Configuration

In SuccessFactors LMS user integration, to configure the connector to treat only the first row as a header, set this property in the connector configuration:

sfuser.connector.input.file.header.skip.records.count=0

---

# ════════════════════════════════════════════════════
# CATEGORY 7 — System Replication
# ════════════════════════════════════════════════════

## S/4HANA to SuccessFactors — Cost Center Constraints and Code Concatenation

In S/4HANA to SuccessFactors Employee Central replication, a cost center cannot be one-to-many with a legal entity in S/4 — this constraint must also be respected in EC. The standard replication job concatenates Controlling Area code and Cost Center code when populating the EC cost center field (for example, Controlling Area 1000 and Cost Center 90000001 becomes 100090000001 in EC). Associations other than Legal Entity are not supported in the standard replication. Every time a full sync of cost centers is performed from S/4 to EC, all cost center associations must be reimported manually.

---

## SuccessFactors to ECP — Point-to-Point Connection Setup

To configure a PTP connection from SuccessFactors to Employee Central Payroll (ECP).

Prerequisites: SF API User must have OData and Metadata permissions. Refer to entry: SuccessFactors API User Required Permissions for CPI Integration.

Step 1 — ECP: TCode HRSFEC_PTP_CONFIG > Set Connection Data > Connect with X.509 Certificate. Enter the SF API URL (for example https://apiXX.successfactors.com). Click Download Public Key and save locally.

Step 2 — SF: Security Center > X.509 Public Certificate Mapping. Upload the public key downloaded from Step 1.
