# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import uuid

import pytest
from sqlalchemy import TEXT, Column, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR
from promptflow._sdk._orm.session import create_or_update_table, support_transaction

TABLENAME = "orm_entity"


def random_string() -> str:
    return str(uuid.uuid4())


def dump(obj, engine) -> None:
    session_maker = sessionmaker(bind=engine)
    with session_maker() as session:
        session.add(obj)
        session.commit()


class SchemaV1(declarative_base()):
    __tablename__ = TABLENAME
    column1 = Column(TEXT, primary_key=True)
    column2 = Column(TEXT)
    __pf_schema_version__ = "1"

    @staticmethod
    def generate(engine) -> None:
        entity = SchemaV1(column1=random_string(), column2=random_string())
        dump(entity, engine)
        return


class SchemaV2(declarative_base()):
    __tablename__ = TABLENAME
    column1 = Column(TEXT, primary_key=True)
    column2 = Column(TEXT)
    column3 = Column(TEXT)
    __pf_schema_version__ = "2"

    @staticmethod
    def generate(engine) -> None:
        entity = SchemaV2(column1=random_string(), column2=random_string(), column3=random_string())
        dump(entity, engine)
        return


class SchemaV3(declarative_base()):
    __tablename__ = TABLENAME
    column1 = Column(TEXT, primary_key=True)
    column2 = Column(TEXT)
    column3 = Column(TEXT)
    column4 = Column(TEXT)
    __pf_schema_version__ = "3"

    @staticmethod
    def generate(engine) -> None:
        entity = SchemaV3(
            column1=random_string(), column2=random_string(), column3=random_string(), column4=random_string()
        )
        dump(entity, engine)
        return


# exactly same schema as SchemaV3
class SchemaV4(declarative_base()):
    __tablename__ = TABLENAME
    column1 = Column(TEXT, primary_key=True)
    column2 = Column(TEXT)
    column3 = Column(TEXT)
    column4 = Column(TEXT)
    __pf_schema_version__ = "4"

    @staticmethod
    def generate(engine) -> None:
        entity = SchemaV4(
            column1=random_string(), column2=random_string(), column3=random_string(), column4=random_string()
        )
        dump(entity, engine)
        return


def mock_use(engine, orm_class, entity_num: int = 1) -> None:
    create_or_update_table(engine, orm_class, TABLENAME)
    for _ in range(entity_num):
        orm_class.generate(engine)


def generate_engine():
    db_path = (HOME_PROMPT_FLOW_DIR / ".test" / f"{uuid.uuid4()}.sqlite").resolve()
    if not db_path.parent.is_dir():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{str(db_path)}", future=True)


@pytest.mark.community_control_plane_sdk_test
@pytest.mark.unittest
class TestSchemaManagement:
    def test_fixed_version(self) -> None:
        engine = generate_engine()
        mock_use(engine, SchemaV3)
        mock_use(engine, SchemaV3, entity_num=2)
        mock_use(engine, SchemaV3, entity_num=3)
        # 1 table
        assert inspect(engine).has_table(TABLENAME)
        # 6 rows
        entities = [entity for entity in sessionmaker(bind=engine)().query(SchemaV3).all()]
        assert len(entities) == 6

    def test_version_upgrade(self) -> None:
        engine = generate_engine()
        mock_use(engine, SchemaV1)
        mock_use(engine, SchemaV2)
        mock_use(engine, SchemaV3)
        # 3 tables: 1 current and 2 legacy
        assert inspect(engine).has_table(TABLENAME)
        assert inspect(engine).has_table(f"{TABLENAME}_v1")
        assert inspect(engine).has_table(f"{TABLENAME}_v2")
        # 2 rows in current table
        entities = [entity for entity in sessionmaker(bind=engine)().query(SchemaV3).all()]
        assert len(entities) == 3

    def test_version_downgrade(self, capfd) -> None:
        engine = generate_engine()
        mock_use(engine, SchemaV3)
        mock_use(engine, SchemaV2)
        mock_use(engine, SchemaV1)
        # 1 table
        assert inspect(engine).has_table(TABLENAME)
        # 2 rows
        entities = [entity for entity in sessionmaker(bind=engine)().query(SchemaV1).all()]
        assert len(entities) == 3
        # with warning message
        out, _ = capfd.readouterr()
        assert "While we will do our best to ensure compatibility, " in out

    def test_version_mixing(self) -> None:
        engine = generate_engine()
        mock_use(engine, SchemaV2, entity_num=2)
        mock_use(engine, SchemaV3, entity_num=3)  # 1 upgrade
        mock_use(engine, SchemaV2, entity_num=1)
        mock_use(engine, SchemaV1, entity_num=4)
        mock_use(engine, SchemaV3, entity_num=2)
        # 2 tables: 1 current and 1 legacy
        assert inspect(engine).has_table(TABLENAME)
        assert inspect(engine).has_table(f"{TABLENAME}_v2")
        # 12(all) rows in current table
        entities = [entity for entity in sessionmaker(bind=engine)().query(SchemaV3).all()]
        assert len(entities) == 12

    def test_version_across_same_schema_version(self, capfd) -> None:
        engine = generate_engine()
        # when 3->4, no warning message
        mock_use(engine, SchemaV3)
        mock_use(engine, SchemaV4)
        out, _ = capfd.readouterr()
        assert "While we will do our best to ensure compatibility, " not in out
        # same schema, no warning message
        mock_use(engine, SchemaV4)
        out, _ = capfd.readouterr()
        assert "While we will do our best to ensure compatibility, " not in out
        # when 4->3, warning message on upgrade should be printed
        mock_use(engine, SchemaV3)
        out, _ = capfd.readouterr()
        assert "While we will do our best to ensure compatibility, " in out

    def test_db_without_schema_info(self) -> None:
        engine = generate_engine()
        # manually create a table to avoid creation of schema_info table
        with engine.begin() as connection:
            connection.execute(text(f"CREATE TABLE {TABLENAME} (column1 TEXT PRIMARY KEY);"))
            connection.execute(
                text(f"INSERT INTO {TABLENAME} (column1) VALUES (:column1);"),
                {"column1": random_string()},
            )
        mock_use(engine, SchemaV3)
        # 2 tables: 1 current and 1 legacy with name containing timestamp
        assert inspect(engine).has_table(TABLENAME)
        # 2 rows in current table
        entities = [entity for entity in sessionmaker(bind=engine)().query(SchemaV3).all()]
        assert len(entities) == 2


@pytest.mark.community_control_plane_sdk_test
@pytest.mark.unittest
class TestTransaction:
    def test_commit(self) -> None:
        engine = generate_engine()
        engine = support_transaction(engine)
        tablename = "transaction_test"
        sql = f"CREATE TABLE {tablename} (id INTEGER PRIMARY KEY);"
        with engine.begin() as connection:
            connection.execute(text(sql))
            connection.commit()
        assert inspect(engine).has_table(tablename)

    def test_rollback(self) -> None:
        engine = generate_engine()
        engine = support_transaction(engine)
        tablename = "transaction_test"
        sql = f"CREATE TABLE {tablename} (id INTEGER PRIMARY KEY);"
        with engine.begin() as connection:
            connection.execute(text(sql))
            connection.rollback()
        assert not inspect(engine).has_table(tablename)

    def test_exception_during_transaction(self) -> None:
        engine = generate_engine()
        engine = support_transaction(engine)
        tablename = "transaction_test"
        sql = f"CREATE TABLE {tablename} (id INTEGER PRIMARY KEY);"
        try:
            with engine.begin() as connection:
                connection.execute(text(sql))
                # raise exception, so that SQLAlchemy should help rollback
                raise Exception("test exception")
        except Exception:
            pass
        assert not inspect(engine).has_table(tablename)
