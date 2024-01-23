from pathlib import Path

import sqlalchemy
from sqlalchemy import TEXT, Column, Index, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


class Span(Base):
    """
    Columns:
    - context
      - trace_id: test of line id
      - span_id: span id
    - parent_id: empty for root span
    - experiment_name: partition id
    - run_name
    - path: working directory/flow_path/experiment_path

    Queries:
    - F5 + Test results of opened directory: experiment_name = None & run_name = None & path.startswith(/path/to/project/)
    - Run: run_name = xx
    - Run + Eval Run: (somehow retrieve names): run_name in (xx, yy, zz...)
    - F5 + Test results of experiment: experiment_name = xx
    """
    __tablename__ = "span"

    span_id = Column(TEXT, primary_key=True)
    trace_id = Column(TEXT)
    parent_id = Column(TEXT, nullable=True)
    # we might not need `experiment_name` if we have partition,
    # then the file name should be `experiment_name` or "default"
    experiment_name = Column(TEXT, nullable=True)
    run_name = Column(TEXT, nullable=True)
    path = Column(TEXT)
    content = Column(TEXT)  # JSON string

    __table_args__ = (
        Index("idx_span_experiment_name", "experiment_name"),
        Index("idx_span_run_name", "run_name"),
    )

    def persist(self) -> None:
        with db_session() as session:
            session.add(self)
            session.commit()


session_maker = None


def support_transaction(engine):
    # workaround to make SQLite support transaction; reference to SQLAlchemy doc:
    # https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#serializable-isolation-savepoints-transactional-ddl
    @event.listens_for(engine, "connect")
    def do_connect(db_api_connection, connection_record):
        # disable pysqlite emitting of the BEGIN statement entirely.
        # also stops it from emitting COMMIT before any DDL.
        db_api_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # emit our own BEGIN
        conn.exec_driver_sql("BEGIN")

    return engine


def db_session() -> Session:
    global session_maker
    if session_maker is not None:
        return session_maker()

    db_path = (Path.cwd().resolve() / "db.sqlite").resolve()
    engine = sqlalchemy.create_engine(f"sqlite:///{db_path.as_posix()}")
    engine = support_transaction(engine)

    try:
        Span.metadata.create_all(engine)
    except OperationalError:
        pass

    session_maker = sessionmaker(bind=engine)
    return session_maker()
