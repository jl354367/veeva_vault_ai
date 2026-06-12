"""
Static Veeva Vault knowledge base.
VAULT_KB: maps topic key → markdown answer string.
KB_ALIASES: maps alternate words/phrases → canonical VAULT_KB key.
"""

VAULT_KB: dict[str, str] = {

    # ── Core Platform ────────────────────────────────────────────────────────

    "vault": (
        "## Veeva Vault\n\n"
        "Veeva Vault is a cloud-based content management and collaboration platform purpose-built for life sciences. "
        "It provides a unified platform for managing documents, data, and processes across clinical, regulatory, quality, "
        "commercial, and medical affairs departments.\n\n"
        "**Key capabilities:**\n"
        "- Document management with version control and audit trail\n"
        "- Configurable document lifecycles and workflows\n"
        "- Role-based security and atomic-level permissions\n"
        "- Built-in e-signature (21 CFR Part 11 / Annex 11 compliant)\n"
        "- Vault-to-Vault crosslinks for multi-vault organizations\n"
        "- REST API and Vault Java SDK for integrations\n\n"
        "**Vault applications include:** RIM Vault, QualityDocs, PromoMats, eTMF, CTMS, MedInquiry, Safety, and more."
    ),

    "document": (
        "## Documents in Vault\n\n"
        "A document in Vault is the primary content object. Every document has:\n\n"
        "- **Document type / subtype / classification** — defines the metadata fields, lifecycle, and rendition settings\n"
        "- **Version** — Vault tracks major (1.0, 2.0) and minor (0.1, 0.2) versions; only one version is 'current'\n"
        "- **Lifecycle state** — e.g. Draft → In Review → Approved → Obsolete\n"
        "- **Rendition** — a viewable format (PDF) generated automatically from the source file\n"
        "- **Annotations** — comments, highlights, and replies anchored to rendition pages\n\n"
        "**Document fields** store metadata such as title, status, product, country, etc. "
        "Fields can be system-defined or custom, and may be required, optional, or read-only depending on lifecycle state."
    ),

    "document type": (
        "## Document Types\n\n"
        "Document types define the structure and behavior of documents in Vault. Each document type specifies:\n\n"
        "- **Metadata fields** — which fields appear and are required\n"
        "- **Lifecycle** — the states and transitions available to documents of this type\n"
        "- **Rendition settings** — whether to auto-generate a PDF viewable rendition\n"
        "- **Subtypes and classifications** — hierarchical sub-groupings within a type\n\n"
        "**Configuration path:** Admin > Configuration > Document Types\n\n"
        "A document type hierarchy looks like:\n"
        "```\n"
        "Document Type\n"
        "  └── Subtype\n"
        "        └── Classification\n"
        "```\n"
        "Each level can override field visibility, lifecycle assignment, and rendition behavior."
    ),

    "lifecycle": (
        "## Document Lifecycles\n\n"
        "A lifecycle controls the states a document can be in and the transitions between them. "
        "It enforces review and approval processes.\n\n"
        "**Key components:**\n"
        "- **States** — e.g. Draft, In Review, Approved, Superseded, Obsolete\n"
        "- **Transitions** — actions that move a document from one state to another (e.g. 'Submit for Review')\n"
        "- **Entry actions** — automatic actions triggered when entering a state (e.g. notify users, lock document)\n"
        "- **User actions** — manual actions available in a state (e.g. 'Approve', 'Reject')\n"
        "- **Role permissions** — which roles can perform which actions in each state\n\n"
        "**Lifecycle states control:**\n"
        "- Who can view, edit, or delete the document\n"
        "- Which fields are editable vs. read-only\n"
        "- Whether the document can be checked out\n\n"
        "**Configuration path:** Admin > Configuration > Lifecycles"
    ),

    "workflow": (
        "## Workflows\n\n"
        "Workflows automate multi-step review, approval, and task assignment processes in Vault.\n\n"
        "**Workflow types:**\n"
        "- **Document workflows** — triggered on a document (e.g. approval workflow)\n"
        "- **Object workflows** — triggered on a Vault object record\n\n"
        "**Key components:**\n"
        "- **Steps** — sequential or parallel tasks assigned to participants\n"
        "- **Participants** — users or groups assigned to complete each step\n"
        "- **Due dates** — configurable deadlines per step\n"
        "- **Instructions** — guidance shown to participants\n"
        "- **Controls** — conditions that determine the workflow path (e.g. verdicts)\n\n"
        "**Workflow verdicts** (e.g. Approve / Reject) can trigger lifecycle transitions or branch the workflow.\n\n"
        "**Configuration path:** Admin > Configuration > Workflows"
    ),

    "role": (
        "## Roles in Vault\n\n"
        "Roles define what users can do within Vault. There are two types:\n\n"
        "**1. Security Profiles (global roles)**\n"
        "- Control access to Vault admin features, objects, and global settings\n"
        "- Assigned to users at the user level\n\n"
        "**2. Document Roles (document-level)**\n"
        "- Control what users can do on specific documents\n"
        "- Common roles: Owner, Editor, Reviewer, Approver, Viewer\n"
        "- Applied through lifecycle state permissions or explicit document role assignment\n\n"
        "**Role permissions on a lifecycle state include:**\n"
        "- View content, View document, Edit document\n"
        "- Perform lifecycle actions (e.g. promote, obsolete)\n"
        "- Manage annotations, Manage document security\n\n"
        "**Configuration path:** Admin > Configuration > Roles (document roles), Admin > Users & Groups > Security Profiles"
    ),

    "user": (
        "## Users in Vault\n\n"
        "Users are individual accounts that can log in and interact with Vault.\n\n"
        "**User attributes:**\n"
        "- Username, email, first/last name, locale, timezone\n"
        "- Security profile — controls admin and object-level permissions\n"
        "- License type — Full User, External User, Read-Only User\n"
        "- Group membership — used for document role assignment and workflow participation\n\n"
        "**User management:**\n"
        "- Admin > Users & Groups > Users\n"
        "- Users can be created manually, via CSV import, or provisioned through SSO/SCIM\n\n"
        "**External users** have limited access, typically for external collaborators (e.g. vendors, CROs). "
        "They cannot access admin settings and have restricted vault navigation."
    ),

    "group": (
        "## Groups in Vault\n\n"
        "Groups are collections of users used to simplify security and workflow assignment.\n\n"
        "**Group types:**\n"
        "- **Static groups** — manually maintained list of users\n"
        "- **Dynamic groups** — automatically populated based on user attribute criteria (e.g. all users in a department)\n\n"
        "**Groups are used for:**\n"
        "- Assigning document roles (e.g. all QA reviewers get the Reviewer role)\n"
        "- Workflow participant assignment\n"
        "- Notification subscriptions\n\n"
        "**Configuration path:** Admin > Users & Groups > Groups"
    ),

    "security profile": (
        "## Security Profiles\n\n"
        "Security profiles control what users can access and do at the vault-wide level, "
        "independent of document-level roles.\n\n"
        "**Security profile permissions include:**\n"
        "- Access to Admin settings\n"
        "- Object CRUD permissions (create, read, edit, delete on Vault objects)\n"
        "- Document tab visibility\n"
        "- Ability to create, import, or export documents\n"
        "- Access to reports, dashboards, and library views\n\n"
        "**Common profiles:** Vault Owner, Business Admin, Read-Only User, External User\n\n"
        "**Configuration path:** Admin > Users & Groups > Security Profiles\n\n"
        "Security profiles are assigned per-user. A user's effective permissions are the combination "
        "of their security profile AND their document role permissions on each specific document."
    ),

    "atomic security": (
        "## Atomic Security\n\n"
        "Atomic Security is Vault's fine-grained document permission system. "
        "It allows explicit permission grants or denials at the individual document level, "
        "overriding the default role-based permissions.\n\n"
        "**How it works:**\n"
        "- On any document, you can grant or deny specific permissions to specific users or groups\n"
        "- Atomic rules override lifecycle state role permissions for the targeted users\n"
        "- A deny always takes precedence over a grant\n\n"
        "**Atomic permissions include:**\n"
        "- View Document, View Content, Edit Document, Edit Content\n"
        "- Manage Document Security, Manage Annotations\n"
        "- Perform lifecycle user actions\n\n"
        "**Use cases:**\n"
        "- Restricting a sensitive document to a specific sub-team\n"
        "- Granting temporary edit access to an external collaborator\n\n"
        "Atomic Security must be enabled in the Vault configuration before use."
    ),

    "sharing rule": (
        "## Sharing Rules\n\n"
        "Sharing Rules in Vault control which object records a user can see and interact with. "
        "They extend or restrict the default visibility defined by the security profile.\n\n"
        "**How sharing rules work:**\n"
        "- Each Vault object (e.g. Product, Study, Site) can have sharing rules configured\n"
        "- A sharing rule defines: *who* gets access, *which records* they can see, and *what* they can do\n"
        "- Rules are evaluated at record retrieval time — users only see records matching their sharing rules\n\n"
        "**Sharing rule components:**\n"
        "- **Source** — the security profile or group to which the rule applies\n"
        "- **Criteria** — field-based filter that determines which records are shared (e.g. Country = 'US')\n"
        "- **Permission** — Read, Edit, or Full Control on matching records\n\n"
        "**Example:**\n"
        "A sharing rule can grant the 'US Medical Team' group Edit access to all Product records "
        "where Country__c = 'United States'.\n\n"
        "**Configuration path:** Admin > Configuration > Objects > [Object Name] > Sharing Settings"
    ),

    "permission": (
        "## Permissions in Vault\n\n"
        "Vault uses a layered permission model:\n\n"
        "**1. Security Profile** — global vault-level permissions (admin access, object CRUD)\n"
        "**2. Document Role + Lifecycle State** — document-level permissions per state\n"
        "**3. Atomic Security** — document-level overrides for specific users/groups\n"
        "**4. Object Sharing Rules** — record-level access for Vault objects\n\n"
        "**Permission evaluation order:**\n"
        "1. Atomic deny → always wins\n"
        "2. Atomic grant → overrides role-based permissions\n"
        "3. Document role permissions in current lifecycle state\n"
        "4. Security profile permissions\n\n"
        "A user needs permissions at each layer to perform an action."
    ),

    "field": (
        "## Fields in Vault\n\n"
        "Fields store metadata on documents and objects. They are the building blocks of Vault's data model.\n\n"
        "**Field types:**\n"
        "- Text, Long Text, Number, Date, DateTime, Yes/No (Boolean)\n"
        "- Picklist (single or multi-value)\n"
        "- Lookup (reference to another object or document)\n"
        "- Formula — calculated value based on other fields\n"
        "- Object reference — link to a Vault object record\n\n"
        "**Field properties:**\n"
        "- Required / Optional\n"
        "- Unique\n"
        "- Default value\n"
        "- Editable by lifecycle state (controlled via lifecycle role permissions)\n\n"
        "**Document fields** are configured per document type. "
        "**Object fields** are configured on the object definition.\n\n"
        "**Configuration path:** Admin > Configuration > Document Fields (or Objects > [Object] > Fields)"
    ),

    "picklist": (
        "## Picklists\n\n"
        "Picklists are predefined lists of values that users can select from when filling in a field.\n\n"
        "**Types:**\n"
        "- **Single-select picklist** — user picks one value\n"
        "- **Multi-select picklist** — user can pick multiple values\n\n"
        "**Picklist management:**\n"
        "- Picklists are shared across the vault — one picklist can be used by multiple fields\n"
        "- Values can be active or inactive (inactive values still show on existing records)\n"
        "- Values can be ordered\n\n"
        "**Configuration path:** Admin > Configuration > Picklists\n\n"
        "**Best practice:** Use picklists for standardized values (e.g. document status, region, product type) "
        "to ensure data consistency across your vault."
    ),

    "object": (
        "## Vault Objects\n\n"
        "Vault Objects are structured data records (similar to database tables or Salesforce objects). "
        "They are used to store business data that relates to documents.\n\n"
        "**Common objects:** Product, Study, Site, Country, Person, Submission, etc.\n\n"
        "**Object components:**\n"
        "- **Fields** — metadata attributes on each record\n"
        "- **Relationships** — links between objects (lookup, master-detail)\n"
        "- **Object lifecycles** — states and transitions for object records\n"
        "- **Object workflows** — automated processes on object records\n"
        "- **Sharing rules** — control which users see which records\n\n"
        "**Custom objects** can be created to model your specific business data.\n\n"
        "**Configuration path:** Admin > Configuration > Objects"
    ),

    "binder": (
        "## Binders\n\n"
        "Binders are containers that organize multiple documents into a structured hierarchy, "
        "similar to a folder or a submission dossier.\n\n"
        "**Key features:**\n"
        "- Contain sections and sub-sections with documents\n"
        "- Have their own lifecycle independent of the documents inside\n"
        "- Support binding rules — automatically add documents matching criteria to a binder\n"
        "- Used heavily in RIM (eCTD submissions) and eTMF\n\n"
        "**Binder sections** are created manually or via templates. "
        "Documents are linked into binders (the original document is not moved).\n\n"
        "**Binder templates** allow pre-defining the section structure for reuse."
    ),

    "rendition": (
        "## Renditions\n\n"
        "A rendition is an alternative representation of a document — most commonly a PDF viewable version "
        "auto-generated from the source file (Word, Excel, PowerPoint, etc.).\n\n"
        "**Rendition types:**\n"
        "- **Viewable rendition** — PDF used for in-browser viewing and annotations\n"
        "- **Approved rendition** — the locked, signed PDF after approval\n"
        "- **Overlaid rendition** — viewable with annotations overlaid\n\n"
        "**Auto-rendition:** Vault can automatically convert source files to PDF on upload.\n\n"
        "**Watermarks:** Renditions can be configured to show watermarks (e.g. 'DRAFT', 'CONFIDENTIAL') "
        "based on lifecycle state.\n\n"
        "**Configuration path:** Admin > Configuration > Document Types > [Type] > Rendition Settings"
    ),

    "annotation": (
        "## Annotations\n\n"
        "Annotations are comments, highlights, and notes that reviewers add to document renditions in Vault.\n\n"
        "**Annotation types:**\n"
        "- **Note** — free-text comment anchored to a page location\n"
        "- **Highlight** — color-coded text highlight\n"
        "- **Reply** — threaded response to an existing annotation\n"
        "- **Line**, **Arrow**, **Rectangle** — drawing annotations\n\n"
        "**Annotation workflow:**\n"
        "- Reviewers add annotations during the review lifecycle state\n"
        "- Authors can respond to or resolve annotations\n"
        "- Annotations are tracked per user and can be reported on\n\n"
        "**Annotation permissions** are controlled by document role permissions in each lifecycle state."
    ),

    "sandbox": (
        "## Sandbox Vaults\n\n"
        "A Sandbox is a non-production copy of your Vault used for testing configuration changes "
        "before deploying to production.\n\n"
        "**Sandbox types:**\n"
        "- **Configuration sandbox** — copy of your production vault configuration (no production data)\n"
        "- **Developer sandbox** — lightweight environment for SDK/API development\n\n"
        "**What's copied from production:**\n"
        "- Document types, lifecycles, workflows, fields, objects\n"
        "- Security profiles, roles, groups\n"
        "- Report and dashboard definitions\n\n"
        "**What's NOT copied:**\n"
        "- Production documents and data\n"
        "- User passwords\n\n"
        "**Sandbox refresh** resets the sandbox to a new copy of production configuration.\n\n"
        "**Best practice:** Always test configuration changes in sandbox before deploying to production."
    ),

    "audit trail": (
        "## Audit Trail\n\n"
        "Vault's audit trail provides a comprehensive, tamper-proof log of all actions taken on documents, "
        "objects, and system configuration.\n\n"
        "**Audit trail types:**\n"
        "- **Document audit trail** — all actions on a document (view, edit, download, lifecycle change, e-sign)\n"
        "- **Object audit trail** — changes to object records\n"
        "- **Login audit trail** — user login/logout events\n"
        "- **System audit trail** — configuration changes by admins\n\n"
        "**Each audit entry records:**\n"
        "- Timestamp, user, action type, old value, new value\n\n"
        "**Audit reports** can be exported as CSV for compliance reporting.\n\n"
        "**Regulatory relevance:** The audit trail supports 21 CFR Part 11 and Annex 11 compliance requirements."
    ),

    "electronic signature": (
        "## Electronic Signatures (e-Signatures)\n\n"
        "Vault supports 21 CFR Part 11 and Annex 11 compliant electronic signatures.\n\n"
        "**E-signature process:**\n"
        "1. A user action (e.g. 'Approve') triggers a signature requirement\n"
        "2. The user enters their username and password to sign\n"
        "3. Vault records the signature with a timestamp and meaning (e.g. 'Approved')\n"
        "4. The signature is permanently attached to the document version\n\n"
        "**E-signature settings:**\n"
        "- Configured on lifecycle state user actions\n"
        "- Can require a reason/meaning for the signature\n"
        "- Multi-signature workflows supported (multiple signers required)\n\n"
        "**Signature manifest** — a PDF attachment listing all signers, timestamps, and meanings — "
        "is automatically generated and attached to signed documents."
    ),

    "sso": (
        "## Single Sign-On (SSO)\n\n"
        "Vault supports SAML 2.0-based Single Sign-On (SSO) to allow users to authenticate "
        "using their corporate identity provider (IdP) instead of a Vault-specific password.\n\n"
        "**Supported SSO providers:** Okta, Azure AD, Ping Identity, ADFS, and any SAML 2.0 compliant IdP.\n\n"
        "**SSO configuration includes:**\n"
        "- IdP metadata URL or XML upload\n"
        "- Attribute mapping (email, first name, last name)\n"
        "- Just-in-time (JIT) user provisioning option\n\n"
        "**SCIM provisioning** can be used alongside SSO to automatically create, update, and deactivate "
        "Vault users based on IdP directory changes.\n\n"
        "**Configuration path:** Admin > Settings > Single Sign-On"
    ),

    "vql": (
        "## Vault Query Language (VQL)\n\n"
        "VQL is Vault's SQL-like query language used to retrieve document and object data via the Vault REST API.\n\n"
        "**Basic syntax:**\n"
        "```sql\n"
        "SELECT id, name__v, status__v FROM documents WHERE type__v = 'Regulatory'\n"
        "```\n\n"
        "**VQL capabilities:**\n"
        "- Query documents, objects, users, groups\n"
        "- Filter with WHERE clauses (equality, CONTAINS, LIKE, IN, BETWEEN)\n"
        "- ORDER BY, LIMIT, OFFSET for pagination\n"
        "- JOIN-like lookups via object relationships\n\n"
        "**Common system fields:**\n"
        "- `id` — unique record ID\n"
        "- `name__v` — name of the record\n"
        "- `status__v` — lifecycle state\n"
        "- `created_by__v`, `modified_by__v` — user references\n\n"
        "VQL is used in the Vault REST API, reports, and integrations."
    ),

    "api": (
        "## Vault REST API\n\n"
        "The Vault REST API allows programmatic access to Vault documents, objects, and configuration.\n\n"
        "**Key API capabilities:**\n"
        "- CRUD operations on documents and objects\n"
        "- Lifecycle action execution\n"
        "- Document upload and download\n"
        "- User and group management\n"
        "- VQL queries\n"
        "- Bulk operations (batch create, update, delete)\n\n"
        "**Authentication:** Session ID (obtained via /auth endpoint) or OAuth 2.0\n\n"
        "**Base URL format:** `https://{vault_domain}/api/{version}/`\n\n"
        "**API versioning:** Vault API versions follow the pattern `v24.1`, `v24.2`, etc. "
        "Each version is supported for 2+ years.\n\n"
        "**API documentation:** developer.veevavault.com"
    ),

    "sdk": (
        "## Vault Java SDK\n\n"
        "The Vault Java SDK allows developers to build custom code that runs directly within Vault, "
        "extending its functionality without external integrations.\n\n"
        "**SDK use cases:**\n"
        "- Custom triggers (entry/exit actions on lifecycle states)\n"
        "- Custom user actions (buttons on documents or objects)\n"
        "- Custom workflow steps\n"
        "- Custom jobs (scheduled background processes)\n"
        "- Custom record actions on objects\n\n"
        "**SDK code** is written in Java, packaged as a JAR, and deployed to Vault via Admin > Deployment.\n\n"
        "**SDK classes:** TriggerInfo, DocumentTriggerContext, ObjectRecordTriggerContext, "
        "UserDefinedClassInfo, VaultCollections\n\n"
        "**Sandbox testing:** Always test SDK code in a sandbox vault before deploying to production."
    ),

    "integration": (
        "## Vault Integrations\n\n"
        "Vault supports multiple integration patterns to connect with external systems.\n\n"
        "**Integration methods:**\n"
        "- **Vault REST API** — HTTP-based CRUD, VQL queries, file operations\n"
        "- **Vault Java SDK** — server-side custom code inside Vault\n"
        "- **Vault Loader** — bulk CSV-based import/export tool for documents and object records\n"
        "- **Spark Messaging** — event-driven integration using Vault's messaging framework\n"
        "- **Crosslink** — read-only document sharing between two Vault instances\n\n"
        "**Common integrations:**\n"
        "- Veeva CRM ↔ Vault (for PromoMats MLR workflow)\n"
        "- Veeva Network ↔ Vault (for HCP/HCO data)\n"
        "- CTMS ↔ eTMF Vault (site and study data sync)\n"
        "- SAP / ERP systems ↔ Vault Quality\n\n"
        "**Configuration path:** Admin > Settings > Integrations"
    ),

    "crosslink": (
        "## Crosslinks\n\n"
        "A Crosslink is a Vault feature that creates a read-only reference to a document in another Vault. "
        "It allows users in one vault to view content owned and managed in a different vault.\n\n"
        "**How crosslinks work:**\n"
        "- The source vault owns the document and controls its lifecycle\n"
        "- The destination vault sees a crosslink — a pointer to the source document\n"
        "- Users in the destination vault can view (not edit) the crosslinked document\n"
        "- When the source document is updated, the crosslink automatically reflects the change\n\n"
        "**Use cases:**\n"
        "- Sharing approved training documents from QualityDocs into eTMF or PromoMats\n"
        "- Regulatory submissions referencing approved clinical study reports\n\n"
        "**Configuration path:** Admin > Settings > Vault-to-Vault Integration"
    ),

    "report": (
        "## Reports in Vault\n\n"
        "Reports allow users to query and display document and object data in a tabular format.\n\n"
        "**Report types:**\n"
        "- **Document reports** — query documents by type, lifecycle state, field values, etc.\n"
        "- **Object reports** — query object records and their fields\n"
        "- **Relationship reports** — combine data across related objects\n\n"
        "**Report features:**\n"
        "- Filter, sort, and group by fields\n"
        "- Aggregate functions (count, sum, avg, min, max)\n"
        "- Scheduling — automatically email reports on a schedule\n"
        "- Export to CSV or Excel\n\n"
        "**Dashboard widgets** can display report data as charts and tables on a configurable dashboard.\n\n"
        "**Configuration path:** Reports tab > New Report"
    ),

    "formula field": (
        "## Formula Fields\n\n"
        "Formula fields compute their value automatically based on an expression using other field values.\n\n"
        "**Supported formula types:**\n"
        "- Text concatenation: `name__v + ' - ' + status__v`\n"
        "- Date arithmetic: `DATEADD(expiry_date__c, -30)` (30 days before expiry)\n"
        "- Conditional: `IF(country__c = 'US', 'FDA', 'EMA')`\n"
        "- Numeric: `quantity__c * unit_price__c`\n\n"
        "**Formula fields are read-only** — users cannot manually edit them.\n\n"
        "**Use cases:**\n"
        "- Auto-generate document titles from multiple fields\n"
        "- Calculate due dates\n"
        "- Derive regulatory pathway from product and region\n\n"
        "**Configuration path:** Admin > Configuration > Document Fields (or Objects > [Object] > Fields)"
    ),

    "layout": (
        "## Layouts\n\n"
        "Layouts control which fields are displayed on a document or object record page, "
        "and how they are arranged.\n\n"
        "**Layout types:**\n"
        "- **Document layouts** — metadata panel layout when viewing/editing a document\n"
        "- **Object layouts** — record detail page layout for object records\n\n"
        "**Layout sections** group related fields together with optional headers.\n\n"
        "**Field visibility in layouts** can be conditional — fields appear only when certain criteria are met "
        "(e.g. show 'Clinical Phase' field only when Document Type = 'Clinical Report').\n\n"
        "**Layouts are assigned** to security profiles or document types, so different users can see "
        "different sets of fields.\n\n"
        "**Configuration path:** Admin > Configuration > Document Layouts (or Objects > [Object] > Layouts)"
    ),

    "subscription": (
        "## Subscriptions (Notifications)\n\n"
        "Subscriptions allow users to receive email or in-app notifications when specific events occur.\n\n"
        "**Subscribable events:**\n"
        "- Document state change (e.g. document moves to Approved)\n"
        "- New document added to a folder or library\n"
        "- Object record created or updated\n"
        "- Workflow task assigned to me\n\n"
        "**Subscription types:**\n"
        "- **User subscriptions** — individual users opt in\n"
        "- **Auto-subscriptions** — configured by admins to automatically subscribe users based on role or criteria\n\n"
        "**Configuration path:** User Profile > Subscriptions (for user-level), "
        "Admin > Configuration > Auto-Subscriptions (for admin-level)"
    ),

    "dynamic access control": (
        "## Dynamic Access Control (DAC)\n\n"
        "Dynamic Access Control automatically assigns document roles based on field values on the document, "
        "without requiring manual role assignment.\n\n"
        "**How DAC works:**\n"
        "- Rules are defined: 'If field X = value Y, then assign role Z to group/user W'\n"
        "- When a document is created or updated, Vault evaluates the rules and assigns roles automatically\n"
        "- Roles update dynamically if the triggering field value changes\n\n"
        "**Example:**\n"
        "If Product = 'Drug A' and Region = 'US', automatically assign the 'US Drug A Team' group as Reviewers.\n\n"
        "**Use cases:**\n"
        "- Large organizations with complex, product/region-based access requirements\n"
        "- Reducing manual document security management overhead\n\n"
        "**Configuration path:** Admin > Configuration > Dynamic Access Control"
    ),

    # ── RIM ──────────────────────────────────────────────────────────────────

    "rim": (
        "## RIM Vault (Regulatory Information Management)\n\n"
        "RIM Vault is Veeva's application for managing regulatory submissions, registrations, and activities.\n\n"
        "**RIM Vault modules:**\n"
        "- **Submissions** — manage dossier content for health authority submissions (eCTD, non-eCTD)\n"
        "- **Registrations** — track product registrations, approvals, and commitments across countries\n"
        "- **Submissions Archive** — store and search published submission packages\n"
        "- **Publishing** — compile and publish eCTD sequences\n\n"
        "**Key concepts:**\n"
        "- **Content Plan** — hierarchical plan linking submission sections to documents\n"
        "- **eCTD** — electronic Common Technical Document format for regulatory submissions\n"
        "- **Sequence** — a numbered submission package sent to a health authority\n"
        "- **Application** — regulatory application (e.g. NDA, MAA) tracked in RIM\n\n"
        "**Integration:** RIM Vault integrates with Veeva Vault PromoMats and eTMF for content reuse."
    ),

    "ectd": (
        "## eCTD (Electronic Common Technical Document)\n\n"
        "The eCTD is a standard format for submitting regulatory dossiers to health authorities (FDA, EMA, etc.).\n\n"
        "**eCTD structure (Modules 1–5):**\n"
        "- **Module 1** — Regional Administrative Information (varies by region)\n"
        "- **Module 2** — Summaries (QOS, Clinical Overview, etc.)\n"
        "- **Module 3** — Quality (CMC)\n"
        "- **Module 4** — Non-clinical Study Reports\n"
        "- **Module 5** — Clinical Study Reports\n\n"
        "**RIM Vault eCTD capabilities:**\n"
        "- Build and manage eCTD sequences with Vault's publishing tool\n"
        "- Track lifecycle of each eCTD document\n"
        "- Publish validated eCTD packages for health authority submission\n"
        "- Archive submitted sequences with full audit trail\n\n"
        "**Supported formats:** eCTD v3.2.2 (ICH), regional variations (EU Module 1, US Module 1, etc.)"
    ),

    "content plan": (
        "## Content Plans\n\n"
        "A Content Plan is a hierarchical structure in RIM Vault that maps submission requirements to documents.\n\n"
        "**Content Plan structure:**\n"
        "- **Content Plan** — top-level plan for a submission or regulatory activity\n"
        "- **Sections** — folders mirroring the eCTD or dossier structure\n"
        "- **Items** — individual document slots that link to actual Vault documents\n\n"
        "**Content Plan uses:**\n"
        "- Track which documents are ready, in review, or missing for a submission\n"
        "- Enforce completeness before publishing\n"
        "- Reuse documents across multiple submissions via crosslinks\n\n"
        "**Content Plan status** rolls up from item → section → plan, showing overall readiness at a glance."
    ),

    # ── Clinical ─────────────────────────────────────────────────────────────

    "etmf": (
        "## eTMF Vault (Electronic Trial Master File)\n\n"
        "eTMF Vault manages clinical trial documentation throughout the trial lifecycle, "
        "ensuring inspection readiness at all times.\n\n"
        "**eTMF structure:**\n"
        "- Organized according to TMF Reference Model zones and sections\n"
        "- Documents are assigned to studies, sites, and countries\n"
        "- Milestones track expected document delivery dates\n\n"
        "**Key eTMF capabilities:**\n"
        "- **TMF completeness metrics** — track which expected documents are filed, missing, or overdue\n"
        "- **Inspection readiness** — quality review workflows to ensure documents meet standards\n"
        "- **Site activation** — track document requirements for site activation\n"
        "- **Real-time dashboards** — TMF health status by study, site, country\n\n"
        "**Integration:** eTMF integrates with CTMS for study/site data, and with EDC systems."
    ),

    "ctms": (
        "## CTMS (Clinical Trial Management System)\n\n"
        "Veeva CTMS is used to manage clinical trial operations, including site management, "
        "patient enrollment, and financial management.\n\n"
        "**CTMS capabilities:**\n"
        "- Site management — track site status, contacts, and agreements\n"
        "- Patient enrollment — enrollment metrics and visit tracking\n"
        "- Financial management — budgets, payments, and reconciliation\n"
        "- Monitoring — site monitoring visit reports and action items\n\n"
        "**CTMS integrates with:**\n"
        "- eTMF Vault — study and site data flows to eTMF for document filing\n"
        "- SiteVault — site-level view of trial documents and activities\n"
        "- EDC systems — enrollment data"
    ),

    # ── Quality ───────────────────────────────────────────────────────────────

    "qualitydocs": (
        "## QualityDocs\n\n"
        "Veeva QualityDocs is a Vault application for managing controlled documents in a GxP environment.\n\n"
        "**Managed document types:**\n"
        "- SOPs (Standard Operating Procedures)\n"
        "- Policies, work instructions, forms, templates\n"
        "- Validation documentation\n\n"
        "**QualityDocs capabilities:**\n"
        "- Controlled document lifecycle (Draft → Review → Approved → Effective → Obsolete)\n"
        "- Periodic review reminders and workflows\n"
        "- Training assignments — automatically assign training tasks when SOPs are approved\n"
        "- Multi-site distribution tracking\n"
        "- Full audit trail for 21 CFR Part 11 / Annex 11 compliance\n\n"
        "**Training module** integrates with QualityDocs to deliver and track SOP-based training."
    ),

    "quality": (
        "## Vault Quality\n\n"
        "Vault Quality is a suite of applications for quality management in life sciences.\n\n"
        "**Vault Quality applications:**\n"
        "- **QualityDocs** — controlled document management\n"
        "- **QMS (Quality Management System)** — deviations, CAPAs, change controls, complaints\n"
        "- **Training** — role-based training assignment and tracking\n"
        "- **Station Manager** — manufacturing shop-floor document display\n\n"
        "**QMS key processes:**\n"
        "- Deviation / OOS (Out of Specification) management\n"
        "- CAPA (Corrective and Preventive Action) tracking\n"
        "- Change Control management\n"
        "- Audit management\n"
        "- Complaint handling\n\n"
        "**Compliance:** Designed for FDA 21 CFR Part 11, EU Annex 11, ISO 13485, and GxP environments."
    ),

    "training": (
        "## Vault Training\n\n"
        "Vault Training is a module that assigns and tracks training requirements for employees, "
        "typically linked to controlled documents in QualityDocs.\n\n"
        "**How training works:**\n"
        "1. A training requirement is created and linked to a document (e.g. SOP)\n"
        "2. Training is assigned to users or groups based on role or job function\n"
        "3. Users complete training by reading the document and acknowledging (e-signature)\n"
        "4. Training records are stored with full audit trail\n\n"
        "**Auto-assignment:** When a new version of a controlled document is approved, "
        "Vault can automatically create new training assignments for all affected personnel.\n\n"
        "**Training curricula** group related training requirements for specific roles."
    ),

    # ── PromoMats ─────────────────────────────────────────────────────────────

    "promomat": (
        "## PromoMats Vault\n\n"
        "Veeva PromoMats is a Vault application for managing promotional and medical content "
        "through the Medical-Legal-Regulatory (MLR) review and approval process.\n\n"
        "**PromoMats capabilities:**\n"
        "- MLR review workflow (Medical, Legal, Regulatory review and approval)\n"
        "- Claims management — track and substantiate product claims\n"
        "- Content plan management — plan promotional materials by brand and market\n"
        "- Auto-approval — route pre-approved content modules automatically\n"
        "- Content expiry — automatically expire approved materials on a set date\n"
        "- Veeva CRM integration — distribute approved content to field reps\n\n"
        "**MLR workflow** typically flows: Draft → Medical Review → Legal Review → Regulatory Review → Approved\n\n"
        "**Integration:** PromoMats integrates with Veeva CRM for content distribution to field reps "
        "and with Veeva Network for HCP/HCO data."
    ),

    "mlr": (
        "## MLR Review (Medical-Legal-Regulatory)\n\n"
        "MLR review is the process by which promotional and medical content is reviewed and approved "
        "by Medical, Legal, and Regulatory teams before use.\n\n"
        "**MLR workflow in PromoMats:**\n"
        "1. **Draft** — content creator develops the material\n"
        "2. **Medical Review** — medical team reviews for scientific accuracy\n"
        "3. **Legal Review** — legal team reviews for compliance\n"
        "4. **Regulatory Review** — regulatory team reviews for regulatory compliance\n"
        "5. **Approved** — material is cleared for use\n\n"
        "**Parallel vs. sequential review:** Steps can run in parallel or sequentially depending on configuration.\n\n"
        "**Vault annotations** allow reviewers to comment directly on the document rendition.\n\n"
        "**Claims linking:** Claims referenced in a document can be linked to their substantiation data."
    ),

    # ── Safety ────────────────────────────────────────────────────────────────

    "safety": (
        "## Vault Safety\n\n"
        "Vault Safety is Veeva's pharmacovigilance platform for managing adverse event reporting "
        "and signal management.\n\n"
        "**Vault Safety capabilities:**\n"
        "- Adverse event (AE) case intake and processing\n"
        "- MedDRA coding\n"
        "- Regulatory reporting — E2B submissions to health authorities\n"
        "- Signal management — detect and evaluate safety signals\n"
        "- Aggregate report support (PSUR, PBRER, DSUR)\n\n"
        "**Integration:** Vault Safety integrates with MedInquiry for medical inquiry management "
        "and with external safety databases."
    ),

    # ── Compliance ────────────────────────────────────────────────────────────

    "21 cfr part 11": (
        "## 21 CFR Part 11\n\n"
        "21 CFR Part 11 is the FDA regulation that defines criteria under which electronic records and "
        "electronic signatures are considered trustworthy and equivalent to paper records.\n\n"
        "**Key requirements:**\n"
        "- **Audit trail** — all record creation, modification, and deletion must be logged\n"
        "- **Electronic signatures** — must be unique to the individual, require identity verification, "
        "and be linked to the signed record\n"
        "- **System validation** — the system must be validated to ensure accuracy and reliability\n"
        "- **Access controls** — only authorized users can create, modify, or delete records\n"
        "- **Record retention** — electronic records must be retained and retrievable\n\n"
        "**Vault compliance:** Vault is designed to meet 21 CFR Part 11 requirements with its built-in "
        "audit trail, e-signature capabilities, access controls, and GxP-validated infrastructure."
    ),

    "annex 11": (
        "## EU GMP Annex 11\n\n"
        "EU GMP Annex 11 is the European regulatory guidance on computerized systems used in GMP environments.\n\n"
        "**Key requirements (similar to 21 CFR Part 11):**\n"
        "- System validation and change control\n"
        "- Data integrity and audit trails\n"
        "- Electronic signatures\n"
        "- Backup and recovery\n"
        "- Security and access controls\n"
        "- Supplier/vendor assessments for cloud systems\n\n"
        "**Vault compliance:** Veeva provides GxP documentation packages (IQ/OQ evidence, "
        "risk assessments) to support customer Annex 11 compliance activities."
    ),

    "data integrity": (
        "## Data Integrity in Vault\n\n"
        "Data integrity ensures that data is complete, consistent, accurate, and trustworthy throughout its lifecycle — "
        "a core GxP and regulatory requirement (ALCOA+: Attributable, Legible, Contemporaneous, Original, Accurate).\n\n"
        "**Vault data integrity controls:**\n"
        "- Comprehensive audit trail — all changes are logged with user, timestamp, old/new values\n"
        "- Version control — all document versions are preserved, not overwritten\n"
        "- Electronic signatures — actions are attributed to specific users\n"
        "- Access controls — only authorized users can modify records\n"
        "- System validation — Vault's infrastructure is validated by Veeva\n"
        "- Lock/supersede — prevents modification of approved documents without a new version\n\n"
        "**ALCOA+ mapping:**\n"
        "- Attributable → audit trail with user\n"
        "- Legible → document renditions\n"
        "- Contemporaneous → system timestamps\n"
        "- Original → version control\n"
        "- Accurate → validation controls"
    ),

    "data model": (
        "## Vault Data Model\n\n"
        "Vault's data model consists of two primary content types:\n\n"
        "**1. Documents**\n"
        "- Unstructured content (files) with associated metadata fields\n"
        "- Organized by document type hierarchy (type > subtype > classification)\n"
        "- Subject to lifecycle, workflow, and role-based security\n\n"
        "**2. Objects**\n"
        "- Structured data records (like database tables)\n"
        "- Have fields, relationships, lifecycles, and sharing rules\n"
        "- Examples: Product, Study, Site, Country, Person\n\n"
        "**Relationships:**\n"
        "- **Lookup** — document or object references another object record\n"
        "- **Parent-child** — master-detail relationship between object records\n"
        "- **Binder-document** — documents linked into binder sections\n"
        "- **Crosslink** — read-only reference to a document in another vault\n\n"
        "The data model is fully configurable through the Admin interface."
    ),

    "validation": (
        "## Vault Validation\n\n"
        "Veeva Vault follows a Software as a Service (SaaS) shared responsibility model for GxP validation.\n\n"
        "**Veeva's responsibilities:**\n"
        "- Platform-level IQ (Installation Qualification) — Veeva performs and provides documentation\n"
        "- OQ (Operational Qualification) — Veeva provides test scripts and evidence\n"
        "- Infrastructure validation — data centers, security controls\n\n"
        "**Customer's responsibilities:**\n"
        "- PQ (Performance Qualification) — customers validate their specific configuration\n"
        "- CSV (Computer System Validation) — customers maintain validation packages\n"
        "- Configuration change control — validate changes before deploying to production\n\n"
        "**Vault's sandbox environment** supports the test/validate-before-production approach.\n\n"
        "**Veeva provides:** Pre-written OQ test scripts, IQ documentation, and GxP documentation packages "
        "to reduce customer validation effort."
    ),

}

# ─── Alias map ────────────────────────────────────────────────────────────────
KB_ALIASES: dict[str, str] = {
    # Plurals and common variations
    "vaults": "vault",
    "documents": "document",
    "docs": "document",
    "document types": "document type",
    "doc type": "document type",
    "lifecycles": "lifecycle",
    "lc": "lifecycle",
    "workflows": "workflow",
    "wf": "workflow",
    "roles": "role",
    "users": "user",
    "groups": "group",
    "fields": "field",
    "picklists": "picklist",
    "pick list": "picklist",
    "objects": "object",
    "binders": "binder",
    "renditions": "rendition",
    "annotations": "annotation",
    "sandboxes": "sandbox",
    "reports": "report",
    "layouts": "layout",
    "subscriptions": "subscription",
    "permissions": "permission",
    "integrations": "integration",
    "crosslinks": "crosslink",
    "apis": "api",
    "sdks": "sdk",

    # Common abbreviations / alternate names
    "security profiles": "security profile",
    "security profile": "security profile",
    "atomic": "atomic security",
    "dac": "dynamic access control",
    "dynamic access": "dynamic access control",
    "esig": "electronic signature",
    "esignature": "electronic signature",
    "e-sig": "electronic signature",
    "e-signature": "electronic signature",
    "electronic sig": "electronic signature",
    "sign": "electronic signature",
    "single sign on": "sso",
    "sso": "sso",
    "saml": "sso",
    "sharing rules": "sharing rule",
    "sharing": "sharing rule",
    "share rule": "sharing rule",
    "audit": "audit trail",
    "audit log": "audit trail",
    "audit history": "audit trail",
    "formula": "formula field",
    "formula fields": "formula field",
    "calculated field": "formula field",

    # Products
    "promomats": "promomat",
    "promotional materials": "promomat",
    "mlr": "mlr",
    "medical legal regulatory": "mlr",
    "qualitydocs": "qualitydocs",
    "quality docs": "qualitydocs",
    "qms": "quality",
    "quality management": "quality",
    "qms vault": "quality",
    "station manager": "quality",
    "etmf": "etmf",
    "tmf": "etmf",
    "trial master file": "etmf",
    "electronic trial master file": "etmf",
    "ctms": "ctms",
    "clinical trial management": "ctms",
    "rim": "rim",
    "regulatory information management": "rim",
    "ectd": "ectd",
    "e-ctd": "ectd",
    "electronic ctd": "ectd",
    "content plans": "content plan",

    # Regulatory
    "21 cfr": "21 cfr part 11",
    "cfr part 11": "21 cfr part 11",
    "part 11": "21 cfr part 11",
    "cfr11": "21 cfr part 11",
    "annex11": "annex 11",
    "eu gmp": "annex 11",
    "gxp": "validation",
    "csv": "validation",
    "computer system validation": "validation",

    # Tech
    "vql": "vql",
    "vault query language": "vql",
    "rest api": "api",
    "vault api": "api",
    "java sdk": "sdk",
    "vault sdk": "sdk",
    "loader": "integration",
    "vault loader": "integration",
    "spark": "integration",
    "spark messaging": "integration",
    "veeva crm": "integration",
    "veeva network": "integration",
}
