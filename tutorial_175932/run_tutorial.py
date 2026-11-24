"""Execute the DataCamp exercises against a dedicated Neo4j database."""
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import neo4j
from neo4j import GraphDatabase
from neo4j.time import DateTime

from ingest_football_data import (
    load_data, create_indexes, ingest_matches, ingest_goals, ingest_shootouts, make_match_id,
)


def top_scorers(tx, tournament, limit):
    result = tx.run(
        """MATCH (p:Player)-[s:SCORED_IN]->(:Match)-[:PART_OF]->(t:Tournament)
        WHERE t.name = $tournament
        RETURN p.name AS Player, count(s) AS Goals
        ORDER BY Goals DESC, Player LIMIT $limit""",
        tournament=tournament, limit=limit,
    )
    return [row.data() for row in result]


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name('.env'))
    evidence = {
        'executed_at_utc': datetime.now(timezone.utc).isoformat(),
        'tutorial': 'https://www.datacamp.com/tutorial/neo4j-tutorial',
        'dataset_commit': 'b0948cb558c927c357db4067eac5b37b96d0e4bb',
        'source_commit': os.getenv('GITHUB_SHA'),
        'run_url': (f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/actions/runs/"
                    f"{os.environ['GITHUB_RUN_ID']}" if 'GITHUB_RUN_ID' in os.environ else None),
        'python': platform.python_version(),
        'neo4j_driver': neo4j.__version__,
    }
    with GraphDatabase.driver(
        os.environ['NEO4J_URI'],
        auth=(os.environ['NEO4J_USERNAME'], os.environ['NEO4J_PASSWORD']),
    ) as driver:
        driver.verify_connectivity()
        print('Connection successful!', flush=True)
        evidence['connectivity'] = 'passed'
        database = os.getenv('NEO4J_DATABASE', 'neo4j')

        def query(cypher, **parameters):
            records, _, _ = driver.execute_query(cypher, database_=database, **parameters)
            return [r.data() for r in records]

        # A fresh database prevents mixing evidence with unrelated ERP data.
        if query('MATCH (n) RETURN count(n) AS count')[0]['count']:
            raise RuntimeError('Use an empty database dedicated to this tutorial.')
        evidence['server'] = query('CALL dbms.components() YIELD name, versions, edition RETURN name, versions, edition')
        matches, goals, shootouts = load_data()
        evidence['csv_rows'] = {'matches': len(matches), 'goals': len(goals), 'shootouts': len(shootouts)}
        with driver.session(database=database) as session:
            create_indexes(session)
            ingest_matches(session, matches)
            ingest_goals(session, goals)
            ingest_shootouts(session, shootouts)
        evidence['nodes_by_label'] = query('MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY label')
        evidence['relationships_by_type'] = query('MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS count ORDER BY type')
        evidence['world_cup_winner'] = query(
            """MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: 'FIFA World Cup'})
            RETURN t.name AS Team, count(m) AS MatchesWon ORDER BY MatchesWon DESC, Team LIMIT 1"""
        )
        evidence['euro_top_3'] = query(
            """MATCH (t:Team)-[:WON]->(m:Match)-[:PART_OF]->(:Tournament {name: $tournament})
            RETURN t.name AS Team, count(m) AS MatchesWon ORDER BY MatchesWon DESC, Team LIMIT $limit""",
            tournament='UEFA Euro', limit=3,
        )
        created = driver.execute_query(
            """MATCH (t:Team {name: $team})
            CREATE (c:Coach {name: $coach})
            CREATE (c)-[r:COACHES]->(t) SET r.start_date = $start_date""",
            database_=database, team='Argentina', coach='Lionel Scaloni', start_date=DateTime(2018, 6, 1),
        )
        evidence['create_coach'] = {
            'nodes_created': created.summary.counters.nodes_created,
            'relationships_created': created.summary.counters.relationships_created,
        }
        evidence['coach'] = query(
            'MATCH (c:Coach)-[r:COACHES]->(t:Team) RETURN c.name AS coach, t.name AS team, toString(r.start_date) AS start_date'
        )
        # MERGE is executed twice to verify the contrast with CREATE.
        merge_query = "MERGE (:Coach {name: $name})"
        first = driver.execute_query(merge_query, database_=database, name='MERGE demonstration')
        second = driver.execute_query(merge_query, database_=database, name='MERGE demonstration')
        evidence['merge_nodes_created'] = [first.summary.counters.nodes_created, second.summary.counters.nodes_created]
        with driver.session(database=database) as session:
            evidence['world_cup_scorers'] = session.execute_read(top_scorers, 'FIFA World Cup', 5)
        # Independently calculate the expected scorer ranking from the pinned CSVs.
        # This validates the graph against its input instead of a 2024 article value.
        valid_matches = matches.dropna(subset=['home_score', 'away_score'])
        world_cup_ids = set(
            valid_matches[valid_matches['tournament'] == 'FIFA World Cup'].apply(make_match_id, axis=1)
        )
        world_cup_goals = goals[goals.apply(make_match_id, axis=1).isin(world_cup_ids)].copy()
        world_cup_goals['scorer'] = world_cup_goals['scorer'].fillna('Unnamed Player')
        ranking = (world_cup_goals.groupby('scorer').size().reset_index(name='Goals')
                   .rename(columns={'scorer': 'Player'})
                   .sort_values(['Goals', 'Player'], ascending=[False, True]).head(5))
        evidence['expected_scorers_from_csv'] = ranking.to_dict(orient='records')
        print(json.dumps(evidence, indent=2, ensure_ascii=False), flush=True)
        assert evidence['world_cup_winner'][0]['Team'] == 'Brazil'
        assert len(evidence['euro_top_3']) == 3
        assert evidence['create_coach'] == {'nodes_created': 1, 'relationships_created': 1}
        assert evidence['merge_nodes_created'] == [1, 0]
        assert evidence['world_cup_scorers'] == evidence['expected_scorers_from_csv']
        assert sum(r['count'] for r in evidence['nodes_by_label']) > 64000
        assert sum(r['count'] for r in evidence['relationships_by_type']) > 340000
    evidence['status'] = 'passed'
    output = Path(__file__).with_name('evidence')
    output.mkdir(exist_ok=True)
    rendered = json.dumps(evidence, indent=2, ensure_ascii=False)
    (output / 'results.json').write_text(rendered + '\n', encoding='utf-8')
    print(rendered, flush=True)


if __name__ == '__main__':
    main()
