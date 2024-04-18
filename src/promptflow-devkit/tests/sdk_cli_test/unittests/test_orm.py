# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

import ast
import uuid

import pytest
from sqlalchemy import TEXT, Column, create_engine, inspect, text
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from promptflow._sdk._constants import HOME_PROMPT_FLOW_DIR
from promptflow._sdk._errors import WrongTraceSearchExpressionError
from promptflow._sdk._orm.session import create_or_update_table, support_transaction
from promptflow._sdk._orm.trace import LineRun, SearchTranslator

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


@pytest.mark.sdk_test
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


@pytest.mark.sdk_test
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


@pytest.fixture
def memory_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    return sessionmaker(bind=engine)()


@pytest.fixture
def search_trans() -> SearchTranslator:
    return SearchTranslator(model=LineRun)


@pytest.mark.unittest
@pytest.mark.sdk_test
class TestTraceSearchTrans:
    SEARCH_SQL_PREFIX = "SELECT line_runs.line_run_id AS line_runs_line_run_id, line_runs.trace_id AS line_runs_trace_id, line_runs.root_span_id AS line_runs_root_span_id, line_runs.inputs AS line_runs_inputs, line_runs.outputs AS line_runs_outputs, line_runs.start_time AS line_runs_start_time, line_runs.end_time AS line_runs_end_time, line_runs.status AS line_runs_status, line_runs.duration AS line_runs_duration, line_runs.name AS line_runs_name, line_runs.kind AS line_runs_kind, line_runs.cumulative_token_count AS line_runs_cumulative_token_count, line_runs.parent_id AS line_runs_parent_id, line_runs.run AS line_runs_run, line_runs.line_number AS line_runs_line_number, line_runs.experiment AS line_runs_experiment, line_runs.session_id AS line_runs_session_id, line_runs.collection AS line_runs_collection \nFROM line_runs"  # noqa: E501

    def _build_expected_sql(self, condition: str) -> str:
        return f"{self.SEARCH_SQL_PREFIX} \nWHERE {condition}"

    def test_translate_compare_str_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "name == 'web-classification'"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "name = 'web-classification'"

    def test_translate_compare_num_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "name >= 42"  # note that this is only for test, name should be a string
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "name >= 42"

    def test_translate_compare_json_field_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "cumulative_token_count.total > 2000"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "json_extract(cumulative_token_count, '$.total') > 2000"

    def test_translate_compare_field_in_json_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "total > 2000"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "json_extract(cumulative_token_count, '$.total') > 2000"

    def test_translate_compare_with_multiple_comparator_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "100 < prompt <= 2000"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "100 < json_extract(cumulative_token_count, '$.prompt') <= 2000"

    def test_translate_compare_status_complete_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "status == 'complete'"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "status = 'Ok'"

    def test_translate_compare_start_time_to_sql(self, search_trans: SearchTranslator):
        compare_expr = "'2012/12/21' < start_time <= '2024/04/18 18:55:42'"
        ast_compare = ast.parse(compare_expr, mode="eval").body
        sql_condition = search_trans._translate_compare_to_sql(ast_compare)
        assert sql_condition == "'2012-12-21T00:00:00' < start_time <= '2024-04-18T18:55:42'"

    def test_basic_search(self, memory_session: Session, search_trans: SearchTranslator):
        basic_expr = "name == 'web-classification'"
        query = search_trans.translate(session=memory_session, expression=basic_expr)
        expected_condition = "name = 'web-classification'"
        expected_sql = self._build_expected_sql(expected_condition)
        assert expected_sql == str(query)

    def test_search_with_bool(self, memory_session: Session, search_trans: SearchTranslator):
        expr = "name == 'web-classification' and kind == 'LLM'"
        query = search_trans.translate(session=memory_session, expression=expr)
        expected_condition = "name = 'web-classification' AND kind = 'LLM'"
        expected_sql = self._build_expected_sql(expected_condition)
        assert expected_sql == str(query)

    def test_search_with_multiple_bool(self, memory_session: Session, search_trans: SearchTranslator):
        expr = "name == 'web-classification' and total > 2000 and kind != 'Function'"
        query = search_trans.translate(session=memory_session, expression=expr)
        expected_condition = (
            "name = 'web-classification' "
            "AND json_extract(cumulative_token_count, '$.total') > 2000 "
            "AND kind != 'Function' "
            "AND cumulative_token_count IS NOT NULL"
        )
        expected_sql = self._build_expected_sql(expected_condition)
        assert expected_sql == str(query)

    def test_search_with_bracket(self, memory_session: Session, search_trans: SearchTranslator):
        expr = "cumulative_token_count.completion <= 200 and (name == 'web-classification' or kind != 'Flow')"
        query = search_trans.translate(session=memory_session, expression=expr)
        expected_condition = (
            "json_extract(cumulative_token_count, '$.completion') <= 200 "
            "AND (name = 'web-classification' OR kind != 'Flow') "
            "AND cumulative_token_count IS NOT NULL"
        )
        expected_sql = self._build_expected_sql(expected_condition)
        assert expected_sql == str(query)

    def test_search_with_wrong_expr(self, memory_session: Session, search_trans: SearchTranslator):
        test_cases = [
            ("name", "Invalid search expression, currently support Python syntax for search."),
            ("name = 1", "Invalid search expression, currently support Python syntax for search."),
            ("name == '<name>' AND", "Invalid search expression, currently support Python syntax for search."),
            (
                "name in ('<name1>', '<name2>')",
                "Unsupported compare operator, currently support: '==', '!=', '<', '<=', '>' and '>='.",
            ),
            (
                "name is '<name>'",
                "Unsupported compare operator, currently support: '==', '!=', '<', '<=', '>' and '>='.",
            ),
            ("start_time >= 'promptflow'", "Invalid time format: 'promptflow'"),
        ]
        for expr, error_msg in test_cases:
            with pytest.raises(WrongTraceSearchExpressionError) as e:
                search_trans.translate(session=memory_session, expression=expr)
            assert error_msg in str(e)
