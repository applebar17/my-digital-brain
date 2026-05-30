CREATE CONSTRAINT person_id_unique IF NOT EXISTS
FOR (n:Person) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT event_id_unique IF NOT EXISTS
FOR (n:Event) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT place_id_unique IF NOT EXISTS
FOR (n:Place) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT organization_id_unique IF NOT EXISTS
FOR (n:Organization) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT object_id_unique IF NOT EXISTS
FOR (n:Object) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT topic_id_unique IF NOT EXISTS
FOR (n:Topic) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT source_id_unique IF NOT EXISTS
FOR (n:Source) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT source_external_unique IF NOT EXISTS
FOR (n:Source) REQUIRE (n.channel, n.external_id) IS UNIQUE;

CREATE CONSTRAINT claim_id_unique IF NOT EXISTS
FOR (n:Claim) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT perception_id_unique IF NOT EXISTS
FOR (n:Perception) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT relationship_context_id_unique IF NOT EXISTS
FOR (n:RelationshipContext) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT profile_memory_id_unique IF NOT EXISTS
FOR (n:ProfileMemory) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contact_point_id_unique IF NOT EXISTS
FOR (n:ContactPoint) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT external_reference_id_unique IF NOT EXISTS
FOR (n:ExternalReference) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT external_reference_provider_unique IF NOT EXISTS
FOR (n:ExternalReference) REQUIRE (n.provider, n.external_id) IS UNIQUE;

CREATE CONSTRAINT extraction_run_id_unique IF NOT EXISTS
FOR (n:ExtractionRun) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT schema_migration_id_unique IF NOT EXISTS
FOR (n:SchemaMigration) REQUIRE n.id IS UNIQUE;

CREATE INDEX person_normalized_name IF NOT EXISTS
FOR (n:Person) ON (n.normalized_name);

CREATE INDEX place_lookup IF NOT EXISTS
FOR (n:Place) ON (n.normalized_name, n.city, n.country);

CREATE INDEX event_time IF NOT EXISTS
FOR (n:Event) ON (n.started_at, n.ended_at);

CREATE INDEX source_lookup IF NOT EXISTS
FOR (n:Source) ON (n.channel, n.external_id, n.received_at);

CREATE INDEX claim_temporal_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.claim_type, n.valid_from, n.valid_to);

CREATE INDEX perception_lookup IF NOT EXISTS
FOR (n:Perception) ON (n.perception_type, n.emotional_valence);

CREATE INDEX relationship_context_lookup IF NOT EXISTS
FOR (n:RelationshipContext) ON (n.relationship_type, n.status, n.closeness);

CREATE INDEX person_lifecycle_lookup IF NOT EXISTS
FOR (n:Person) ON (n.lifecycle_state);

CREATE INDEX person_privacy_lookup IF NOT EXISTS
FOR (n:Person) ON (n.privacy_level);

CREATE INDEX person_trust_lookup IF NOT EXISTS
FOR (n:Person) ON (n.trust_level);

CREATE INDEX event_lifecycle_lookup IF NOT EXISTS
FOR (n:Event) ON (n.lifecycle_state);

CREATE INDEX event_privacy_lookup IF NOT EXISTS
FOR (n:Event) ON (n.privacy_level);

CREATE INDEX event_trust_lookup IF NOT EXISTS
FOR (n:Event) ON (n.trust_level);

CREATE INDEX place_lifecycle_lookup IF NOT EXISTS
FOR (n:Place) ON (n.lifecycle_state);

CREATE INDEX place_privacy_lookup IF NOT EXISTS
FOR (n:Place) ON (n.privacy_level);

CREATE INDEX place_trust_lookup IF NOT EXISTS
FOR (n:Place) ON (n.trust_level);

CREATE INDEX organization_lifecycle_lookup IF NOT EXISTS
FOR (n:Organization) ON (n.lifecycle_state);

CREATE INDEX organization_privacy_lookup IF NOT EXISTS
FOR (n:Organization) ON (n.privacy_level);

CREATE INDEX organization_trust_lookup IF NOT EXISTS
FOR (n:Organization) ON (n.trust_level);

CREATE INDEX object_lifecycle_lookup IF NOT EXISTS
FOR (n:Object) ON (n.lifecycle_state);

CREATE INDEX object_privacy_lookup IF NOT EXISTS
FOR (n:Object) ON (n.privacy_level);

CREATE INDEX object_trust_lookup IF NOT EXISTS
FOR (n:Object) ON (n.trust_level);

CREATE INDEX topic_lifecycle_lookup IF NOT EXISTS
FOR (n:Topic) ON (n.lifecycle_state);

CREATE INDEX topic_privacy_lookup IF NOT EXISTS
FOR (n:Topic) ON (n.privacy_level);

CREATE INDEX topic_trust_lookup IF NOT EXISTS
FOR (n:Topic) ON (n.trust_level);

CREATE INDEX source_lifecycle_lookup IF NOT EXISTS
FOR (n:Source) ON (n.lifecycle_state);

CREATE INDEX source_privacy_lookup IF NOT EXISTS
FOR (n:Source) ON (n.privacy_level);

CREATE INDEX source_trust_lookup IF NOT EXISTS
FOR (n:Source) ON (n.trust_level);

CREATE INDEX claim_lifecycle_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.lifecycle_state);

CREATE INDEX claim_privacy_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.privacy_level);

CREATE INDEX claim_trust_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.trust_level);

CREATE INDEX perception_lifecycle_lookup IF NOT EXISTS
FOR (n:Perception) ON (n.lifecycle_state);

CREATE INDEX perception_privacy_lookup IF NOT EXISTS
FOR (n:Perception) ON (n.privacy_level);

CREATE INDEX perception_trust_lookup IF NOT EXISTS
FOR (n:Perception) ON (n.trust_level);

CREATE INDEX relationship_context_lifecycle_lookup IF NOT EXISTS
FOR (n:RelationshipContext) ON (n.lifecycle_state);

CREATE INDEX relationship_context_privacy_lookup IF NOT EXISTS
FOR (n:RelationshipContext) ON (n.privacy_level);

CREATE INDEX relationship_context_trust_lookup IF NOT EXISTS
FOR (n:RelationshipContext) ON (n.trust_level);

CREATE INDEX profile_memory_lifecycle_lookup IF NOT EXISTS
FOR (n:ProfileMemory) ON (n.lifecycle_state);

CREATE INDEX profile_memory_privacy_lookup IF NOT EXISTS
FOR (n:ProfileMemory) ON (n.privacy_level);

CREATE INDEX profile_memory_trust_lookup IF NOT EXISTS
FOR (n:ProfileMemory) ON (n.trust_level);
