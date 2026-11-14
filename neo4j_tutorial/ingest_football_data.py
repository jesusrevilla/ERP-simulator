import os
import logging

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

# CSV file paths
results_csv_path = "https://raw.githubusercontent.com/martj42/international_results/refs/heads/master/results.csv"
goalscorers_csv_path = "https://raw.githubusercontent.com/martj42/international_results/refs/heads/master/goalscorers.csv"
shootouts_csv_path = "https://raw.githubusercontent.com/martj42/international_results/refs/heads/master/shootouts.csv"

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BATCH_SIZE = 5000


def load_data():
    logger.info("Loading football data...")

    results_df = pd.read_csv(results_csv_path, parse_dates=["date"])
    goalscorers_df = pd.read_csv(goalscorers_csv_path, parse_dates=["date"])
    shootouts_df = pd.read_csv(shootouts_csv_path, parse_dates=["date"])

    return results_df, goalscorers_df, shootouts_df


def make_match_id(row):
    return (
        f"{row['date'].strftime('%Y-%m-%d')}_"
        f"{row['home_team']}_{row['away_team']}"
    )


def is_true(value):
    if pd.isna(value):
        return False

    return str(value).strip().lower() in ("true", "1", "1.0")


def create_indexes(session):
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (t:Team) ON (t.name)",
        "CREATE INDEX IF NOT EXISTS FOR (m:Match) ON (m.id)",
        "CREATE INDEX IF NOT EXISTS FOR (p:Player) ON (p.name)",
        "CREATE INDEX IF NOT EXISTS FOR (t:Tournament) ON (t.name)",
        "CREATE INDEX IF NOT EXISTS FOR (c:City) ON (c.name)",
        "CREATE INDEX IF NOT EXISTS FOR (c:Country) ON (c.name)",
    ]

    for index in indexes:
        session.run(index)

    logger.info("Indexes created.")


def ingest_matches(session, df):
    df = df.dropna(subset=["home_score", "away_score"])

    query = """
    UNWIND $batch AS row

    MERGE (m:Match {id: row.id})
    SET m.date = date(row.date),
        m.home_score = row.home_score,
        m.away_score = row.away_score,
        m.neutral = row.neutral

    MERGE (home:Team {name: row.home_team})
    MERGE (away:Team {name: row.away_team})
    MERGE (t:Tournament {name: row.tournament})
    MERGE (c:City {name: row.city})
    MERGE (country:Country {name: row.country})

    MERGE (home)-[:PLAYED_HOME]->(m)
    MERGE (away)-[:PLAYED_AWAY]->(m)
    MERGE (m)-[:PART_OF]->(t)
    MERGE (m)-[:PLAYED_IN]->(c)
    MERGE (c)-[:LOCATED_IN]->(country)

    WITH m, home, away,
         row.home_score AS hs,
         row.away_score AS awayScore

    FOREACH (_ IN CASE WHEN hs > awayScore THEN [1] ELSE [] END |
        MERGE (home)-[:WON]->(m)
        MERGE (away)-[:LOST]->(m)
    )

    FOREACH (_ IN CASE WHEN hs < awayScore THEN [1] ELSE [] END |
        MERGE (away)-[:WON]->(m)
        MERGE (home)-[:LOST]->(m)
    )

    FOREACH (_ IN CASE WHEN hs = awayScore THEN [1] ELSE [] END |
        MERGE (home)-[:DREW]->(m)
        MERGE (away)-[:DREW]->(m)
    )
    """

    for i in tqdm(range(0, len(df), BATCH_SIZE), desc="Ingesting matches"):
        batch = df.iloc[i:i + BATCH_SIZE]
        data = []

        for _, row in batch.iterrows():
            match_data = {
                "id": make_match_id(row),
                "date": row["date"].strftime("%Y-%m-%d"),
                "home_score": int(row["home_score"]),
                "away_score": int(row["away_score"]),
                "neutral": is_true(row["neutral"]),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "tournament": row["tournament"],
                "city": row["city"],
                "country": row["country"],
            }

            data.append(match_data)

        if data:
            session.run(query, batch=data)


def ingest_goals(session, df):
    query = """
    UNWIND $batch AS row

    MATCH (m:Match {id: row.id})
    MERGE (p:Player {name: row.scorer})
    MERGE (t:Team {name: row.team})

    MERGE (p)-[s:SCORED_FOR {
        match_id: row.id,
        goal_index: row.goal_index
    }]->(t)

    SET s.minute = row.minute,
        s.own_goal = row.own_goal,
        s.penalty = row.penalty

    MERGE (p)-[r:SCORED_IN {
        match_id: row.id,
        goal_index: row.goal_index
    }]->(m)

    SET r.minute = row.minute,
        r.own_goal = row.own_goal,
        r.penalty = row.penalty
    """

    for i in tqdm(range(0, len(df), BATCH_SIZE), desc="Ingesting goals"):
        batch = df.iloc[i:i + BATCH_SIZE]
        data = []

        for _, row in batch.iterrows():
            if pd.isna(row["date"]):
                continue

            goal_data = {
                "id": make_match_id(row),
                "goal_index": int(row.name),
                "scorer": (
                    str(row["scorer"])
                    if pd.notna(row["scorer"])
                    else "Unnamed Player"
                ),
                "team": row["team"],
                "minute": (
                    float(row["minute"])
                    if pd.notna(row["minute"])
                    else None
                ),
                "own_goal": is_true(row["own_goal"]),
                "penalty": is_true(row["penalty"]),
            }

            data.append(goal_data)

        if data:
            session.run(query, batch=data)


def ingest_shootouts(session, df):
    query = """
    UNWIND $batch AS row

    MATCH (m:Match {id: row.id})
    MATCH (w:Team {name: row.winner})

    MERGE (m)-[s:HAD_SHOOTOUT]->(w)

    SET s.winner = row.winner,
        s.first_shooter = row.first_shooter
    """

    for i in tqdm(range(0, len(df), BATCH_SIZE), desc="Ingesting shootouts"):
        batch = df.iloc[i:i + BATCH_SIZE]
        data = []

        for _, row in batch.iterrows():
            if pd.isna(row["date"]):
                continue

            shootout_data = {
                "id": make_match_id(row),
                "winner": row["winner"],
                "first_shooter": (
                    row["first_shooter"]
                    if pd.notna(row["first_shooter"])
                    else None
                ),
            }

            data.append(shootout_data)

        if data:
            session.run(query, batch=data)


def main():
    load_dotenv()

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    if not uri or not username or not password:
        raise ValueError("Missing Neo4j credentials.")

    results_df, goalscorers_df, shootouts_df = load_data()

    driver = GraphDatabase.driver(
        uri,
        auth=(username, password)
    )

    try:
        driver.verify_connectivity()
        logger.info("Connected to Neo4j Aura successfully!")

        with driver.session() as session:
            create_indexes(session)

            ingest_matches(session, results_df)
            ingest_goals(session, goalscorers_df)
            ingest_shootouts(session, shootouts_df)

        logger.info("Data ingestion completed successfully!")

    finally:
        driver.close()


if __name__ == "__main__":
    main()


