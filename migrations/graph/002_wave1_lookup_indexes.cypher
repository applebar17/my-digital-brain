CREATE INDEX organization_normalized_name IF NOT EXISTS
FOR (n:Organization) ON (n.normalized_name);

CREATE INDEX object_normalized_name IF NOT EXISTS
FOR (n:Object) ON (n.normalized_name);

CREATE INDEX topic_normalized_name IF NOT EXISTS
FOR (n:Topic) ON (n.normalized_name);

CREATE INDEX profile_memory_key_lookup IF NOT EXISTS
FOR (n:ProfileMemory) ON (n.profile_key, n.category);

CREATE INDEX contact_point_lookup IF NOT EXISTS
FOR (n:ContactPoint) ON (n.kind, n.normalized_value);

CREATE INDEX external_reference_url_lookup IF NOT EXISTS
FOR (n:ExternalReference) ON (n.provider, n.url);

CREATE INDEX extraction_run_status_lookup IF NOT EXISTS
FOR (n:ExtractionRun) ON (n.status, n.source_id);

CREATE INDEX person_affective_lookup IF NOT EXISTS
FOR (n:Person) ON (n.emotional_valence);

CREATE INDEX event_affective_lookup IF NOT EXISTS
FOR (n:Event) ON (n.emotional_valence);

CREATE INDEX place_affective_lookup IF NOT EXISTS
FOR (n:Place) ON (n.emotional_valence);

CREATE INDEX organization_affective_lookup IF NOT EXISTS
FOR (n:Organization) ON (n.emotional_valence);

CREATE INDEX object_affective_lookup IF NOT EXISTS
FOR (n:Object) ON (n.emotional_valence);

CREATE INDEX topic_affective_lookup IF NOT EXISTS
FOR (n:Topic) ON (n.emotional_valence);

CREATE INDEX source_affective_lookup IF NOT EXISTS
FOR (n:Source) ON (n.emotional_valence);

CREATE INDEX claim_affective_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.emotional_valence);
