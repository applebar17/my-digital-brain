CREATE CONSTRAINT relationship_state_id_unique IF NOT EXISTS
FOR (n:RelationshipState) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT change_record_id_unique IF NOT EXISTS
FOR (n:ChangeRecord) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT contradiction_record_id_unique IF NOT EXISTS
FOR (n:ContradictionRecord) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT merge_record_id_unique IF NOT EXISTS
FOR (n:MergeRecord) REQUIRE n.id IS UNIQUE;

CREATE INDEX relationship_state_status_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.status, n.is_current);

CREATE INDEX relationship_state_temporal_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.resolved_start, n.resolved_end);

CREATE INDEX relationship_state_lifecycle_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.lifecycle_state);

CREATE INDEX relationship_state_privacy_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.privacy_level);

CREATE INDEX relationship_state_trust_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.trust_level);

CREATE INDEX change_record_target_lookup IF NOT EXISTS
FOR (n:ChangeRecord) ON (n.target_id, n.target_kind);

CREATE INDEX change_record_changed_at_lookup IF NOT EXISTS
FOR (n:ChangeRecord) ON (n.changed_at);

CREATE INDEX change_record_lifecycle_lookup IF NOT EXISTS
FOR (n:ChangeRecord) ON (n.lifecycle_state);

CREATE INDEX contradiction_record_status_lookup IF NOT EXISTS
FOR (n:ContradictionRecord) ON (n.status, n.severity, n.contradiction_type);

CREATE INDEX contradiction_record_detected_lookup IF NOT EXISTS
FOR (n:ContradictionRecord) ON (n.detected_at);

CREATE INDEX contradiction_record_lifecycle_lookup IF NOT EXISTS
FOR (n:ContradictionRecord) ON (n.lifecycle_state);

CREATE INDEX merge_record_status_lookup IF NOT EXISTS
FOR (n:MergeRecord) ON (n.status, n.canonical_node_id);

CREATE INDEX merge_record_merged_at_lookup IF NOT EXISTS
FOR (n:MergeRecord) ON (n.merged_at);

CREATE INDEX merge_record_lifecycle_lookup IF NOT EXISTS
FOR (n:MergeRecord) ON (n.lifecycle_state);

CREATE INDEX person_resolved_time_lookup IF NOT EXISTS
FOR (n:Person) ON (n.resolved_start, n.resolved_end);

CREATE INDEX event_resolved_time_lookup IF NOT EXISTS
FOR (n:Event) ON (n.resolved_start, n.resolved_end);

CREATE INDEX place_resolved_time_lookup IF NOT EXISTS
FOR (n:Place) ON (n.resolved_start, n.resolved_end);

CREATE INDEX claim_resolved_time_lookup IF NOT EXISTS
FOR (n:Claim) ON (n.resolved_start, n.resolved_end);

CREATE INDEX perception_resolved_time_lookup IF NOT EXISTS
FOR (n:Perception) ON (n.resolved_start, n.resolved_end);

CREATE INDEX relationship_context_resolved_time_lookup IF NOT EXISTS
FOR (n:RelationshipContext) ON (n.resolved_start, n.resolved_end);
