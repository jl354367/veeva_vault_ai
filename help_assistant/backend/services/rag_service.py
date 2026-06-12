import json
import os
import re
import math
import chromadb
from chromadb import EmbeddingFunction, Embeddings

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class _FastEmbedFn(EmbeddingFunction):
    """Hash-based bag-of-words embedding — zero downloads, instant startup."""

    DIM = 512

    def __call__(self, input: list[str]) -> Embeddings:  # type: ignore[override]
        result = []
        for text in input:
            vec = [0.0] * self.DIM
            words = re.findall(r"[a-z0-9]+", text.lower())
            for word in words:
                # Two hash seeds for better coverage
                h1 = hash(word) % self.DIM
                h2 = hash(word + "_b") % self.DIM
                vec[h1] += 1.0
                vec[h2] += 0.5
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            result.append([v / norm for v in vec])
        return result

SYSTEM_PROMPTS = {
    "config": (
        "You are VaultBot in Configuration Analysis mode. You are an expert Veeva Vault administrator "
        "helping users understand their specific Vault configuration.\n\n"
        "IMPORTANT BEHAVIOR:\n"
        "- If the user's message is informal, abbreviated, contains typos, or is in any language, "
        "  interpret their intent, rephrase it clearly, then answer.\n"
        "- Always answer even if the phrasing is imperfect — never refuse due to unclear wording.\n"
        "- When analyzing an uploaded config report, provide a structured summary with sections: "
        "  Document Types, Lifecycles, Roles, Workflows, Integrations, and Key Observations.\n"
        "- Cite specific names, counts, and settings from the context.\n"
        "- If information is not in the context, say so clearly and suggest what to look for."
    ),
    "help": (
        "You are a Veeva Help Assistant that answers user questions by searching and using information "
        "from Veeva Help documentation (https://veevavault.help/).\n\n"

        "ANSWER RULES:\n"
        "- Answer based ONLY on the retrieved Veeva Help content provided in the context.\n"
        "- Do NOT rely on pre-trained knowledge if no relevant content is found in the context.\n"
        "- Treat every question as a fresh search query — do not carry over assumptions.\n"
        "- Extract and summarize relevant information from the context snippets.\n"
        "- If multiple context pieces are provided, combine them into one clear answer.\n"
        "- If no relevant information is found in the context, say exactly: "
        "  'I couldn't find relevant information in the Veeva Help documentation.'\n\n"

        "SEARCH & INTERPRETATION:\n"
        "- Interpret the user's question like a search engine (similar to Google or Copilot).\n"
        "- Identify key terms and topics from the question.\n"
        "- Handle variations in wording — synonyms, paraphrasing, typos, informal language.\n"
        "- If the user writes informally or with typos, understand their intent and answer accordingly.\n\n"

        "ANSWER STYLE:\n"
        "- Clear, structured, and concise.\n"
        "- Use **bullet points** for lists and feature summaries.\n"
        "- Use **numbered steps** for procedural / how-to questions.\n"
        "- Use **headers** (##) for multi-section answers.\n"
        "- Do not hallucinate or assume information not present in the context.\n"
        "- Professional but simple tone — no unnecessary filler.\n"
        "- When referencing a Veeva Help page topic, mention it as: "
        "  *Source: veevavault.help – [topic name]*"
    ),
    "onboard": (
        "You are VaultBot in Onboarding mode. You are a friendly senior Veeva consultant helping a "
        "new team member get up to speed on this specific Vault implementation.\n\n"
        "IMPORTANT BEHAVIOR:\n"
        "- If the user's message is informal, abbreviated, contains typos, or is in any language, "
        "  interpret their intent and answer helpfully — never refuse due to unclear wording.\n"
        "- Use the onboarding context to explain the project, team structure, processes, and environment.\n"
        "- Be welcoming and encourage questions.\n"
        "- Explain things in plain language and introduce key Vault terminology with explanations."
    ),
}


class RAGService:
    def __init__(self):
        self.client = chromadb.EphemeralClient()
        self.ef = _FastEmbedFn()
        self.collections: dict = {}
        self._config_data: dict = {}

    def initialize(self):
        self._load_config_collection()
        self._load_help_collection()
        self._load_onboard_collection()

    def _load_config_collection(self):
        col = self.client.get_or_create_collection(
            name="vault_config", embedding_function=self.ef
        )
        config_path = os.path.join(DATA_DIR, "vault_config.json")
        with open(config_path) as f:
            data = json.load(f)
        self._config_data = data

        docs, ids, metas = [], [], []
        idx = 0

        # Flatten each section into searchable text chunks
        docs.append(f"Organization: {data['organization']['name']}. "
                    f"Vault domain: {data['organization']['vault_domain']}. "
                    f"Vault types: {', '.join(data['organization']['vault_types'])}. "
                    f"Total users: {data['organization']['total_users']}. "
                    f"Total documents: {data['organization']['total_documents']}.")
        ids.append(f"cfg_{idx}"); metas.append({"section": "organization"}); idx += 1

        for v in data["vaults"]:
            docs.append(f"Vault: {v['name']} (type: {v['type']}, region: {v['region']}, "
                        f"version: {v['version']}, status: {v['status']}).")
            ids.append(f"cfg_{idx}"); metas.append({"section": "vaults"}); idx += 1

        for dt in data["document_types"]:
            docs.append(f"Document type '{dt['name']}' (label: {dt['label']}) in {dt['vault']} vault. "
                        f"Lifecycle: {dt['lifecycle']}. "
                        f"Subtypes: {', '.join(dt['subtypes']) if dt['subtypes'] else 'none'}. "
                        f"Fields: {', '.join(dt['fields'])}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "document_types"}); idx += 1

        for lc in data["lifecycles"]:
            states = ", ".join(s["name"] for s in lc["states"])
            transitions = ", ".join(f"{t['from']} → {t['to']} ({t['name']})" for t in lc["transitions"])
            docs.append(f"Lifecycle '{lc['name']}' in {lc['vault']} vault. "
                        f"States ({len(lc['states'])}): {states}. "
                        f"Transitions: {transitions}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "lifecycles"}); idx += 1

        for role in data["roles"]:
            docs.append(f"Role '{role['name']}': permissions {', '.join(role['permissions'])}. "
                        f"Document types: {', '.join(role['document_types'])}. "
                        f"Lifecycle actions: {', '.join(role['lifecycle_actions'])}. "
                        f"User count: {role['user_count']}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "roles"}); idx += 1

        for wf in data["workflows"]:
            steps = "; ".join(f"Step {s['step']}: {s['name']} ({s['participants']})" for s in wf["steps"])
            docs.append(f"Workflow '{wf['name']}' in {wf['vault']} vault. Type: {wf['type']}. "
                        f"Steps: {steps}. Active: {wf['active']}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "workflows"}); idx += 1

        for intg in data["integrations"]:
            docs.append(f"Integration: {intg['name']} ({intg['type']}) in {intg['vault']} vault. "
                        f"Data synced: {', '.join(intg['data_synced'])}. "
                        f"Frequency: {intg['frequency']}. Status: {intg['status']}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "integrations"}); idx += 1

        for obj in data["custom_objects"]:
            docs.append(f"Custom object '{obj['name']}': fields {', '.join(obj['fields'])}. "
                        f"Related to: {', '.join(obj['relationships'])}. "
                        f"Records: {obj['record_count']}.")
            ids.append(f"cfg_{idx}"); metas.append({"section": "custom_objects"}); idx += 1

        col.add(documents=docs, ids=ids, metadatas=metas)
        self.collections["config"] = col

    def _load_help_collection(self):
        # Help mode uses LIVE content from veevavault.help — no pre-built data loaded.
        # The "help" key is intentionally left out of self.collections so that
        # query() returns [] for help mode, and the router uses web-fetched content only.
        pass

    def _load_onboard_collection(self):
        col = self.client.get_or_create_collection(
            name="onboarding", embedding_function=self.ef
        )
        onboard_path = os.path.join(DATA_DIR, "onboarding.json")
        with open(onboard_path) as f:
            items = json.load(f)

        docs = [f"{item['title']} ({item['section']}): {item['content']}" for item in items]
        ids = [item["id"] for item in items]
        metas = [{"title": item["title"], "section": item["section"]} for item in items]
        col.add(documents=docs, ids=ids, metadatas=metas)
        self.collections["onboard"] = col

    def query(self, text: str, mode: str, n_results: int = 5) -> list[str]:
        col = self.collections.get(mode)
        if not col:
            return []
        results = col.query(query_texts=[text], n_results=min(n_results, col.count()))
        return results["documents"][0] if results["documents"] else []

    def add_uploaded_document(self, text: str, filename: str) -> int:
        col = self.collections.get("config")
        if not col:
            return 0

        # Split into ~500-char chunks, cap at 4000 so ChromaDB batch limit is never hit
        all_chunks = [text[i:i + 500] for i in range(0, len(text), 500) if text[i:i + 500].strip()]
        chunks = all_chunks[:4000]

        existing_count = col.count()
        ids    = [f"upload_{existing_count + i}" for i in range(len(chunks))]
        metas  = [{"section": "uploaded", "filename": filename} for _ in chunks]

        # Add in safe batches of 500 to stay under ChromaDB's max batch size
        BATCH = 500
        for start in range(0, len(chunks), BATCH):
            col.add(
                documents=chunks[start:start + BATCH],
                ids=ids[start:start + BATCH],
                metadatas=metas[start:start + BATCH],
            )

        return len(chunks)

    def get_system_prompt(self, mode: str) -> str:
        return SYSTEM_PROMPTS.get(mode, SYSTEM_PROMPTS["help"])
