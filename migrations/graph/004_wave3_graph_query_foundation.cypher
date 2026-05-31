CREATE CONSTRAINT animal_id_unique IF NOT EXISTS
FOR (n:Animal) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT social_circle_id_unique IF NOT EXISTS
FOR (n:SocialCircle) REQUIRE n.id IS UNIQUE;

CREATE INDEX animal_normalized_name IF NOT EXISTS
FOR (n:Animal) ON (n.normalized_name);

CREATE INDEX animal_species_lookup IF NOT EXISTS
FOR (n:Animal) ON (n.species);

CREATE INDEX animal_lifecycle_lookup IF NOT EXISTS
FOR (n:Animal) ON (n.lifecycle_state);

CREATE INDEX animal_privacy_lookup IF NOT EXISTS
FOR (n:Animal) ON (n.privacy_level);

CREATE INDEX animal_trust_lookup IF NOT EXISTS
FOR (n:Animal) ON (n.trust_level);

CREATE INDEX animal_resolved_time_lookup IF NOT EXISTS
FOR (n:Animal) ON (n.resolved_start, n.resolved_end);

CREATE INDEX social_circle_normalized_name IF NOT EXISTS
FOR (n:SocialCircle) ON (n.normalized_name);

CREATE INDEX social_circle_type_lookup IF NOT EXISTS
FOR (n:SocialCircle) ON (n.circle_type);

CREATE INDEX social_circle_lifecycle_lookup IF NOT EXISTS
FOR (n:SocialCircle) ON (n.lifecycle_state);

CREATE INDEX social_circle_privacy_lookup IF NOT EXISTS
FOR (n:SocialCircle) ON (n.privacy_level);

CREATE INDEX social_circle_trust_lookup IF NOT EXISTS
FOR (n:SocialCircle) ON (n.trust_level);

CREATE INDEX social_circle_resolved_time_lookup IF NOT EXISTS
FOR (n:SocialCircle) ON (n.resolved_start, n.resolved_end);

CREATE INDEX place_coordinates_lookup IF NOT EXISTS
FOR (n:Place) ON (n.latitude, n.longitude);

CREATE INDEX place_city_country_lookup IF NOT EXISTS
FOR (n:Place) ON (n.city, n.country);

CREATE INDEX source_received_at_lookup IF NOT EXISTS
FOR (n:Source) ON (n.received_at);

CREATE INDEX relationship_state_time_basis_lookup IF NOT EXISTS
FOR (n:RelationshipState) ON (n.time_basis, n.time_precision);
