"""Embeddings + Qdrant: create the collection, index chunks, search."""
import uuid

from qdrant_client import QdrantClient, models

from geoscholar import config


class Embedder:
    """Thin wrapper so the rest of the code doesn't depend on sentence-transformers directly."""

    def __init__(self, model_name=config.EMBED_MODEL):
        from sentence_transformers import SentenceTransformer   # slow import, so done here
        self.model = SentenceTransformer(model_name)

    def count_tokens(self, text):
        return len(self.model.tokenizer.encode(text, add_special_tokens=False))

    def embed_docs(self, texts, batch_size=32):
        return self.model.encode(texts, batch_size=batch_size, normalize_embeddings=True)

    def embed_query(self, text):
        return self.model.encode(config.QUERY_PREFIX + text, normalize_embeddings=True)


def point_id(chunk_id):
    # Qdrant IDs must be integers or UUIDs. uuid5 turns "2410.01234:7" into the
    # same UUID every time, so re-indexing overwrites instead of duplicating.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class Index:
    def __init__(self, embedder, client=None, collection=config.COLLECTION):
        self.embedder = embedder
        self.client = client or QdrantClient(url=config.QDRANT_URL)
        self.collection = collection

    def ensure_collection(self):
        if self.client.collection_exists(self.collection):
            return
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=models.VectorParams(size=config.EMBED_DIM,
                                               distance=models.Distance.COSINE),
        )
        # payload indexes make filtering by these fields fast
        self.client.create_payload_index(self.collection, "paper_id",
                                         models.PayloadSchemaType.KEYWORD)
        self.client.create_payload_index(self.collection, "year",
                                         models.PayloadSchemaType.INTEGER)

    def _paper_filter(self, paper_id):
        return models.Filter(must=[models.FieldCondition(
            key="paper_id", match=models.MatchValue(value=paper_id))])

    def replace_paper(self, paper_id, chunks):
        """Delete a paper's old chunks, then insert the new ones."""
        self.client.delete(self.collection,
                           points_selector=models.FilterSelector(filter=self._paper_filter(paper_id)))
        if not chunks:
            return 0
        vectors = self.embedder.embed_docs([c["embed_text"] for c in chunks])
        points = [
            models.PointStruct(
                id=point_id(c["chunk_id"]),
                vector=[float(x) for x in v],
                payload={k: val for k, val in c.items() if k != "embed_text"},
            )
            for c, v in zip(chunks, vectors)
        ]
        self.client.upsert(self.collection, points=points)
        return len(points)

    def search(self, query, k=5, year_from=None):
        query_filter = None
        if year_from:
            query_filter = models.Filter(must=[models.FieldCondition(
                key="year", range=models.Range(gte=year_from))])
        res = self.client.query_points(
            collection_name=self.collection,
            query=[float(x) for x in self.embedder.embed_query(query)],
            query_filter=query_filter,
            limit=k,
            with_payload=True,
        )
        return [(p.score, p.payload) for p in res.points]

    def count(self):
        return self.client.count(self.collection, exact=True).count