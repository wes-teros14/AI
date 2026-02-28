# 00: Metadata Cheat Sheet

> **Type:** Internal Reference

### Standard Types & Examples

* **Concept**: Theory/Logic. *(e.g., How OData Pagination works)*
* **Guide**: Step-by-step instructions. *(e.g., Setting up a Cloud Connector)*
* **Snippet**: Reusable code/XML. *(e.g., Groovy script for XML parsing)*
* **Solution**: Fix for specific errors. *(e.g., Fixing CPI 401 Unauthorized)*
* **Reference**: Facts/Specs/T-Codes. *(e.g., Tire pressure specs or Transaction codes)*
* **Pattern**: Architecture trade-offs. *(e.g., Field-level vs. Record-level Delta)*
* **Requirement**: Project scope/needs. *(e.g., PAL Project: Sync must be real-time)*
* **Log**: Event records/Minutes. *(e.g., Meeting with client stakeholders)*
* **Rule**: Policies/Regulations. *(e.g., Badminton court queuing rules)*
* **Checklist**: Prep/Workshop questions. *(e.g., Design Workshop Question list)*
* **Discovery**: System behavior findings. *(e.g., `PerPerson` navigation limits, light bulb moments, gotchas)*
* **Task**: Actions/Reminders. *(e.g., Fix Streamlit shuffle logic bug)*

---

# 01: System Aliases and Terminology

> **Tags:** #meta #sap #terminology
> **Type:** Reference

## SAP Integration Suite Equivalents

* **Names:** `Integration Suite`, `CPI`, `SCI`, `SCPI`, `CI`, `IS`

## SAP SuccessFactors Equivalents

* **Names:** `SuccessFactors`, `SFSF`, `SF`

## S/4 Equivalents

* **Names:** `S4`, `S4 HANA`, `S/4`, `S/4 HANA`

## ECC Equivalents

* **Names:** `ECC`, `ERP`

## SAP SuccessFactors Equivalents

* **Names:** `SuccessFactors`, `SFSF`, `SF`

## Employee Central Equivalents

* **Names:** `Employee Central`, `EC`

## SAP SuccessFactors / Employee Central (Interchangeable)

* **Primary Names:** `SuccessFactors`, `SFSF`, `SF`, `Employee Central`, `EC`
* **Note for AI:** Unless a specific non-EC module is mentioned (like LMS or Recruiting), treat all SF aliases as referring to Employee Central.

## SAP Cloud Connector

* **Names:** `SAP Cloud Connector`, `Cloud Connector`, `SCC`

## Employee Central Payroll

* **Names:** `Employee Central Payroll`, `ECP`

## Point to Point Replication

* **Names:** `Point to Point Replication`, `Point-to-Point Replication`, `PTP Replication`

## Business Integration Builder Replication

* **Names:** `Business Integration Builder Replication`, `Business Integration Builder`, `BIB`

## Learning Management System

* **Names:** `Learning Management System`, `LMS`

---

# Integration Terminology and Aliases

> **Date:** 2026-02-27
> **Tags:** #sap #architecture #definitions
> **Type:** Concept

## **Connectivity Synonyms**

When troubleshooting or designing integrations, the following terms are fundamentally linked and often refer to the exact same point of failure in an adapter configuration:
* **`API`:** The overarching framework and authentication layer.
* **`Endpoint`:** The specific target object or function.
* **`URL`:** The absolute text string used to locate the system.
* **`Address`:** The network location or hostname.

---

# Integration Classification: Standard vs. Custom
> **Date:** 2026-02-28
> **Tags:** #sap #architecture #standard #custom #development
> **Keywords:** Standard, Custom, OOTB, Prepackaged, Bespoke, Z-Object, BADI
> **Type:** Concept

## **Classification Definitions**

### **1. Standard (Prepackaged / OOTB)**
* **Definition:** Integration content provided directly by SAP (Out-Of-The-Box).
* **Behavior:** Usually "Read-Only" or restricted. Modifications are only permitted via official extension points like **`BADI`** or specific **`IMG`** configuration.
* **Troubleshooting:** Focus on SAP Service Marketplace, Support Portal, and checking if the latest `Content Version` is deployed in `CPI`.

### **2. Custom (Bespoke / Z-Development)**
* **Definition:** Integration content built from scratch by the project team.
* **Behavior:** Fully flexible and fully owned by the consultant. Includes custom `Groovy` scripts, complex `XSLT`, and unique routing logic.
* **Troubleshooting:** Focus on internal `CPI` message logs, trace mode, and debugging the specific logic mapping.

## **Decision Logic**
When analyzing a requirement:
1. Always check if a **Standard** content exists first to minimize maintenance.
2. Only move to **Custom** development if the requirement cannot be met via **Standard** configuration or **BADI** extensions.


---

# `SCI`/`CPI` Subscription Details

> **Date:** 2026-02-24
> **Tags:** #sap #cpi #licensing
> **Type:** Reference

## SAP Official Documentation

* **SAP Note 2903776:** [View Note on SAP Me](https://me.sap.com/notes/2903776)
* **Context:** Use for verifying tenant provisioning and subscription boundaries.

---

# Workshop: Common Interface Design Questions

> **Date:** 2026-02-24
> **Tags:** #sap #cpi #integration #architecture
> **Type:** Checklist

## Data Scoping Questions

* Full file or Delta only?
* Record level or Field level Delta?
* Do we send effective dates?

## Handling Changes

* Do we send deleted records?
* Timing: Do we send records on the day they become effective or future-dated?

---

# `SuccessFactors` `Compound Employee` API (CE)

> **Date:** 2026-02-24
> **Tags:** #sap #successfactors #sfapi #api
> **Type:** Discovery

## **`Delta`** Behavior

* When using **`parameter=periodDelta`**, the pointer reference is the previous last modified date-time. 
* A snapshot is taken each query; the last modified date-time is the key.

## **`MDF`** Object Limitations

* Only **custom** **`MDF`** can be added to the `Compound Employee` API response/object.
* Only these 3 **standard** **`MDF`** objects are allowed: 
    * `Work Order`
    * `Higher Duty Temp Assignment`
    * `Onboarding Info`

## **Reference**

* **Documentation:** [Extending CE with MDF Objects](https://help.sap.com/docs/successfactors-employee-central/employee-central-compound-employee-api/extending-api-with-mdf-objects?locale=en-US)

---

# `SuccessFactors` OData API Discovery

> **Date:** 2026-02-24
> **Tags:** #sap #successfactors #odata #api
> **Type:** Discovery

## Custom **`MDF`** Navigation Issues

* **Problem:** When data originates from a custom **`MDF`** object, it **cannot** be navigated directly from the **`PerPerson`** entity.
* **Impact:** Because it lacks the navigation path from **`PerPerson`**, these custom objects cannot be configured for **Standard Delta** synchronization.

## **`EmpPayCompRecurring`** Behavior & Logic

* **Logic:** Unlike standard entities, **`EmpPayCompRecurring`** groups all pay components under a single effective date.
* **Effective Date Sharing:** Every pay component assigned to an employee on the same date shares that exact **`startDate`**.
* **Insert Behavior:** When you insert a new pay component record:
    * The system **copies** all existing active pay components to the new insertion date.
    * **Critical Note:** This effectively "refreshes" the start dates for all components in that record.

---

# `Standard` `SuccessFactors` to `S4`/`ERP` `BIB` Replication

> **Date:** 2026-02-24
> **Tags:** #sap #successfactors #S4 #BIB #replication
> **Type:** Discovery

## `Action Reason`

* `Action Reason` in S4 is not required in the replication.


---

# `Standard` `S/4` to `SuccessFactors` Cost Center Replication

> **Date:** 2026-02-24
> **Tags:** #sap #successfactors #S4 #replication
> **Type:** Discovery

## Cost Center to Legal Entity association

* In S4, cost center to legal entity cant be associated one to many, therefore in `EC` it should also not be one to many

## Cost Center code note

* The replication job from `S4` to `EC` will concatenate Controlling Area + Cost Center code

## Association other than Legal Entity are not supported in the standard replication

* Every time you make a full sync from `S4` to `EC`, you need to reimport the cost center associations

---

# `SuccessFactors` API Field Visibility

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #S4 #odata
> **Type:** Discovery

## Standard vs. Custom `MDF` Visibility

* **Custom `MDF`:** Visibility and API access are fully managed via Configure Object Definitions.
* **Standard `MDF`:** Certain fields have "hardcoded" visibility levels. While the object definition can be viewed, some standard fields are governed by Manage Business Configuration (`BCUI`) or Configure Employee Files. 
* **Note:** Always check the API Visibility attribute in the Object Definition; if it is set to "Not Visible," the field will be excluded from the OData metadata even if RBP permissions are granted.
---

# `SuccessFactors` API User Required Permissions

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #api
> **Type:** Reference

## Permissions required under Manage Permission Roles

* General User Permision: User Login, SFAPI user login, Login Method(password)
* Employee Central API: Employee central foundation `SOAP` API
* Employee Central API: Employee central HRIS `SOAP` API
* Employee Central API: Employee central foundation `OData` API(editable)
* Employee Central API: Employee central HRIS `OData` API(editable)
* Manage Integration Tools: Allow admin to access `OData` API through basic authentication
* Manage User: User account `OData` entity
* Metadata Framework: Admin access to `MDF` `OData` API

---

# `ATO` / `STP` 'CPI' Standard Integration

> **Date:** 2026-02-25
> **Tags:** #sap #cpi #integration #ato #stp
> **Type:** Reference, Guide

## Solution for Multiple `ABN`s (Cross Entity Authorization)

* In scenarios with multiple ABNs, one ABN acts as the **Intermediate ABN** (ABN A) to represent other ABNs (ABN B, C, etc.) when submitting STP reports.
* This requires specific permissions in the ATO portal where the organization must authorize ABN A to represent ABN B.

```text
Hi,

The resolution for the multiple ABN issue is as follows:

When you have multiple ABNs, one ABN acts as the Intermediate ABN (ABN A), which represents the remaining ABNs (ABN B) to submit the STP report.

In the ATO portal, your organization needs to provide permission for ABN A to represent ABN B. Additionally, ABN A needs to accept the permission to represent ABN B.

This is called Cross Entity Authorization. You can set this up manually by submitting a form to the ATO (which takes longer), or you can log on to the RAM (Relationship Authorisation Manager) portal to set this up yourself.
```
* **Reference** [GDrive Link](https://drive.google.com/file/d/1-hM8c-mCcrbyvyIQnmp0NlBoW5UGjnT8/view?usp=drive_link)


---

# Fixing issues when `CPI` cannot send `BIB` replication data to `S4` / `ECC`

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #bib #replication #s4
> **Type:** Solution

## **Problem:** Data replication failure to `S4` / `ECC`

When the `BIB` (Business Integration Builder) flow fails to push data, perform the following checks:

### **Solution 1:** Verify Web Service Activation

* Check in `Tcode` **`SICF`** if the path `default_host/sap/bc/srt/scs/sap/` is active.
* **Action:** If it is greyed out, right-click and select **Activate Service**.

### **Solution 2:** Cloud Connector (`SCC`) Access Policy

* Check the access policy in the **SAP Cloud Connector**.
* **Action:** Ensure the resource path is set to **Path and All Sub-paths**. If it is set to "Exact Name," the dynamic `BIB` calls will be blocked.

---

# `SuccessFactors` to `S4` `BIB` Replication

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #bib #replication #s4
> **Type:** Discovery

## `BP Sync`

* When data is sent to `S4` (`HR Mini-master`) via `BIB` Replication, `S4` will then create a `Business Partner` via `BP sync job`.

---


# `SuccessFactors` to `ECP` Connection (PTP)

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #ecp #replication #ptp
> **Type:** Guide

## **Prerequisites**

* Ensure the **API User** in `SFSF` has sufficient permissions for OData and Metadata access.

## **Implementation Steps**

### **Step 1:** ECP Configuration

1. In `ECP`, go to `Tcode`: **`HRSFEC_PTP_CONFIG`**.
2. Select **Set Connection Data** and then select **Connect with X.509 certificate**.
3. Enter the `SFSF` API URL (e.g., `https://apiXX.successfactors.com`).
4. Click **Download Public Key** to save the certificate locally.

### **Step 2:** SuccessFactors Security Setup

1. Log in to `SFSF` and go to the **Security Center**.
2. Select **X.509 Public Certificate Mapping**.
3. Upload the public key downloaded from `ECP`.

---

# `SAPRouter`

> **Date:** 2026-02-25
> **Tags:** #sap #successfactors #bib #replication #s4
> **Type:** Discovery

## `SAPRouter` uses

* In order to access `S4` via `SAPGUI` the `S4 Private` / `On-premise`, we need to have `SAPRouter` installed in the `S4` system

---

# SuccessFactors User Intergration to LMS

> **Date:** 2026-02-27
> **Tags:** #sap #successfactors #lms
> **Type:** Discovery

## Enable Single Header on the `LMS` input file

* set this variable `sfuser.connector.input.file.header.skip.records.count=0`

---

# SuccessFactors Timesheet Integration

> **Date:** 2026-02-27
> **Tags:** #sap #successfactors #time
> **Type:** Discovery

## Clock-in/Clock-out coming from external system

* Clock-in/Clock-out coming from external system will be stored in `OData` entity: `ExternalTimeData`.
* Clock-in/Clock-out coming from `SF` UI will be stored in `OData`entity: `EmployeeTime`

---

# `SuccessFactors` `Employee Central`

> **Date:** 2026-02-28
> **Tags:** #sap #successfactors #ec
> **Type:** Discovery

## Dropdown / `picklist` values

* Some dropdown lists, like `National ID Card Type`, are **not** `Picklists`.
* **Configuration Path:** * Go to `Manage Business Configuration`.
    * Navigate to `HRIS Elements` -> `nationalIdCard`-> `nationalIdCard_XXX` (where `XXX` is the Country Code). 
* **Technical Note:** These values are governed by the **Country-Specific Data Model** rather than the `Picklist Center`.

---

# Posting `Foundation Data` from External Syatem going to `SuccessFactors` `Employee Central`

> **Date:** 2026-02-28
> **Tags:** #sap #successfactors #integration
> **Type:** Discovery

## `Foundation Object` Names

* Make sure that during the upsert/insert the payload also includes the `defaultValue` and translations.

---