import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, MetaData, Table, create_engine
from sqlalchemy.orm import Session, scoped_session, sessionmaker


class BeetsDatabase:
    engine: Engine
    session_factory: scoped_session[Session]
    path: Path

    def __init__(self, db_path: Path | str):
        if isinstance(db_path, str):
            db_path = Path(db_path)
        self.path = db_path

        if not self.path.is_file() or not os.access(db_path, os.R_OK):
            raise FileNotFoundError(
                f"Beets database file not found or not readable: {db_path}"
            )

        uri = f"sqlite:///{db_path}"
        self.engine = create_engine(uri)
        self.session_factory = scoped_session(sessionmaker(bind=self.engine))

    @contextmanager
    def session(self, session: Session | None = None) -> Generator[Session, None, None]:
        """Databases session as context.

        Makes sure sessions are closed at the end.
        If an existing session is provided, it will not be closed at the end.
        This allows to wrap multiple `with db.session()` blocks around each other
        without closing the outer session.

        Example:
        ```
        db = BeetsDatabase("path/to/beets.db")
        with db.session() as session:
            tag.foo = "bar"
            session.merge(tag)
            return tag.to_dict()

        existingSession = session_factory()
        with db.session(session) as s:
            tag.foo = "bar"
            s.merge(tag)
            return tag.to_dict()
        ```
        """
        is_outermost = session is None

        if session is None:
            session = self.session_factory()

        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            if is_outermost:
                session.close()

    def get_table(self, name: str) -> Table:
        """Get a table by name."""
        metadata = MetaData()
        metadata.reflect(bind=self.engine)
        table = Table(name, metadata, autoload_with=self.engine)
        return table

    def get_tables(self) -> list[Table]:
        """Get all tables in the database."""
        metadata = MetaData()
        metadata.reflect(bind=self.engine)
        return list(metadata.tables.values())

    def __del__(self):
        """Close the database connection when the object is deleted."""
        if self.session_factory:
            self.session_factory.remove()
        if self.engine:
            self.engine.dispose()
