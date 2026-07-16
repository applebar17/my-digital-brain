MATCH (n:Person)
WHERE n.is_owner IS NULL
SET n.is_owner = false;

CREATE INDEX person_owner_lookup IF NOT EXISTS
FOR (n:Person) ON (n.is_owner);
