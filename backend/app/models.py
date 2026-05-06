"""SQLAlchemy models for all database tables."""
from sqlalchemy import Column, Integer, Text, Float, Date, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Tournament(Base):
    __tablename__ = "tournaments"

    id = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    course_name = Column(Text, nullable=False)
    city = Column(Text)
    state = Column(Text)
    country = Column(Text)
    par = Column(Integer)
    yardage = Column(Integer)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    season = Column(Integer, nullable=False)
    purse = Column(Float)


class TournamentResult(Base):
    __tablename__ = "tournament_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Text, ForeignKey("tournaments.id"), nullable=False)
    season = Column(Integer, nullable=False)
    player_id = Column(Text, nullable=False)
    player_name = Column(Text, nullable=False)
    position = Column(Text)
    total_score = Column(Integer)
    par_relative_score = Column(Integer)
    rounds_played = Column(Integer)

    __table_args__ = (
        UniqueConstraint("tournament_id", "season", "player_id"),
    )


class PlayerStat(Base):
    __tablename__ = "player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Text, nullable=False)
    player_name = Column(Text, nullable=False)
    season = Column(Integer, nullable=False)
    stat_category = Column(Text, nullable=False)
    stat_value = Column(Float)
    stat_rank = Column(Integer)

    __table_args__ = (
        UniqueConstraint("player_id", "season", "stat_category"),
    )


class CourseStatWeight(Base):
    __tablename__ = "course_stat_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Text, ForeignKey("tournaments.id"), nullable=False)
    stat_category = Column(Text, nullable=False)
    weight = Column(Float, nullable=False)
    explanation = Column(Text)
    computed_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("tournament_id", "stat_category"),
    )


class PlayerFitScore(Base):
    __tablename__ = "player_fit_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Text, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Text, nullable=False)
    player_name = Column(Text, nullable=False)
    composite_score = Column(Float, nullable=False)
    world_ranking = Column(Integer)
    fedex_ranking = Column(Integer)
    computed_at = Column(DateTime, default=func.now())

    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id"),
    )


class EventPlayerStat(Base):
    """Player stats for a specific tournament event (week-level stats)."""
    __tablename__ = "event_player_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Text, nullable=False)  # e.g., "R2024012"
    season = Column(Integer, nullable=False)
    player_id = Column(Text, nullable=False)
    player_name = Column(Text, nullable=False)
    stat_category = Column(Text, nullable=False)
    stat_value = Column(Float)
    stat_rank = Column(Integer)

    __table_args__ = (
        UniqueConstraint("tournament_id", "season", "player_id", "stat_category"),
    )


class TournamentField(Base):
    """Players in the official field/entry list for a tournament."""
    __tablename__ = "tournament_field"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tournament_id = Column(Text, ForeignKey("tournaments.id"), nullable=False)
    player_id = Column(Text, nullable=False)
    player_name = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("tournament_id", "player_id"),
    )
