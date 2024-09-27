graph [
  directed 1
  node [
    id 0
    label "stellar"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 1
    label "stellar.stellar"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 2
    label "stellar.stellar.app"
    type "module"
    code "import logging&#10;import os&#10;import sys&#10;import click&#10;from functools import partial&#10;&#10;from .config import load_config&#10;from .models import Snapshot, Table, Base&#10;from .operations import (&#10;    copy_database,&#10;    create_database,&#10;    database_exists,&#10;    remove_database,&#10;    rename_database,&#10;    terminate_database_connections,&#10;    list_of_databases,&#10;)&#10;from sqlalchemy import create_engine&#10;from sqlalchemy.orm import sessionmaker&#10;from sqlalchemy.exc import ProgrammingError&#10;from psutil import pid_exists&#10;&#10;&#10;__version__ = '0.4.5'&#10;logger = logging.getLogger(__name__)&#10;&#10;&#10;class Operations(object):&#10;    def __init__(self, raw_connection, config):&#10;        self.terminate_database_connections = partial(&#10;            terminate_database_connections, raw_connection&#10;        )&#10;        self.create_database = partial(create_database, raw_connection)&#10;        self.copy_database = partial(copy_database, raw_connection)&#10;        self.database_exists = partial(database_exists, raw_connection)&#10;        self.rename_database = partial(rename_database, raw_connection)&#10;        self.remove_database = partial(remove_database, raw_connection)&#10;        self.list_of_databases = partial(list_of_databases, raw_connection)&#10;&#10;&#10;class Stellar(object):&#10;    def __init__(self):&#10;        logger.debug('Initialized Stellar()')&#10;        self.load_config()&#10;        self.init_database()&#10;&#10;    def load_config(self):&#10;        self.config = load_config()&#10;        logging.basicConfig(level=self.config['logging'])&#10;&#10;    def init_database(self):&#10;        self.raw_db = create_engine(self.config['url'], echo=False)&#10;        self.raw_conn = self.raw_db.connect()&#10;        self.operations = Operations(self.raw_conn, self.config)&#10;&#10;        try:&#10;            self.raw_conn.connection.set_isolation_level(0)&#10;        except AttributeError:&#10;            logger.info('Could not set isolation level to 0')&#10;&#10;        self.db = create_engine(self.config['stellar_url'], echo=False)&#10;        self.db.session = sessionmaker(bind=self.db)()&#10;        self.raw_db.session = sessionmaker(bind=self.raw_db)()&#10;        tables_missing = self.create_stellar_database()&#10;&#10;        self.create_stellar_tables()&#10;&#10;        # logger.getLogger('sqlalchemy.engine').setLevel(logger.WARN)&#10;&#10;    def create_stellar_database(self):&#10;        if not self.operations.database_exists('stellar_data'):&#10;            self.operations.create_database('stellar_data')&#10;            return True&#10;        else:&#10;            return False&#10;&#10;    def create_stellar_tables(self):&#10;        Base.metadata.create_all(self.db)&#10;        self.db.session.commit()&#10;&#10;    def get_snapshot(self, snapshot_name):&#10;        return self.db.session.query(Snapshot).filter(&#10;            Snapshot.snapshot_name == snapshot_name,&#10;            Snapshot.project_name == self.config['project_name']&#10;        ).first()&#10;&#10;    def get_snapshots(self):&#10;        return self.db.session.query(Snapshot).filter(&#10;            Snapshot.project_name == self.config['project_name']&#10;        ).order_by(&#10;            Snapshot.created_at.desc()&#10;        ).all()&#10;&#10;    def get_latest_snapshot(self):&#10;        return self.db.session.query(Snapshot).filter(&#10;            Snapshot.project_name == self.config['project_name']&#10;        ).order_by(Snapshot.created_at.desc()).first()&#10;&#10;    def create_snapshot(self, snapshot_name, before_copy=None):&#10;        snapshot = Snapshot(&#10;            snapshot_name=snapshot_name,&#10;            project_name=self.config['project_name']&#10;        )&#10;        self.db.session.add(snapshot)&#10;        self.db.session.flush()&#10;&#10;        for table_name in self.config['tracked_databases']:&#10;            if before_copy:&#10;                before_copy(table_name)&#10;            table = Table(&#10;                table_name=table_name,&#10;                snapshot=snapshot&#10;            )&#10;            logger.debug('Copying %s to %s' % (&#10;                table_name,&#10;                table.get_table_name('master')&#10;            ))&#10;            self.operations.copy_database(&#10;                table_name,&#10;                table.get_table_name('master')&#10;            )&#10;            self.db.session.add(table)&#10;        self.db.session.commit()&#10;&#10;        self.start_background_slave_copy(snapshot)&#10;&#10;    def remove_snapshot(self, snapshot):&#10;        for table in snapshot.tables:&#10;            try:&#10;                self.operations.remove_database(&#10;                    table.get_table_name('master')&#10;                )&#10;            except ProgrammingError:&#10;                pass&#10;            try:&#10;                self.operations.remove_database(&#10;                    table.get_table_name('slave')&#10;                )&#10;            except ProgrammingError:&#10;                pass&#10;            self.db.session.delete(table)&#10;        self.db.session.delete(snapshot)&#10;        self.db.session.commit()&#10;&#10;    def rename_snapshot(self, snapshot, new_name):&#10;        snapshot.snapshot_name = new_name&#10;        self.db.session.commit()&#10;&#10;    def restore(self, snapshot):&#10;        for table in snapshot.tables:&#10;            click.echo(&#34;Restoring database %s&#34; % table.table_name)&#10;            if not self.operations.database_exists(&#10;                table.get_table_name('slave')&#10;            ):&#10;                click.echo(&#10;                    &#34;Database %s does not exist.&#34;&#10;                    % table.get_table_name('slave')&#10;                )&#10;                sys.exit(1)&#10;            try:&#10;                self.operations.remove_database(table.table_name)&#10;            except ProgrammingError:&#10;                logger.warn('Database %s does not exist.' % table.table_name)&#10;            self.operations.rename_database(&#10;                table.get_table_name('slave'),&#10;                table.table_name&#10;            )&#10;        snapshot.worker_pid = 1&#10;        self.db.session.commit()&#10;&#10;        self.start_background_slave_copy(snapshot)&#10;&#10;    def start_background_slave_copy(self, snapshot):&#10;        logger.debug('Starting background slave copy')&#10;        snapshot_id = snapshot.id&#10;&#10;        self.raw_conn.close()&#10;        self.raw_db.session.close()&#10;        self.db.session.close()&#10;&#10;        pid = os.fork() if hasattr(os, 'fork') else None&#10;        if pid:&#10;            return&#10;&#10;        self.init_database()&#10;        self.operations = Operations(self.raw_conn, self.config)&#10;&#10;        snapshot = self.db.session.query(Snapshot).get(snapshot_id)&#10;        snapshot.worker_pid = os.getpid()&#10;        self.db.session.commit()&#10;        self.inline_slave_copy(snapshot)&#10;        sys.exit()&#10;&#10;    def inline_slave_copy(self, snapshot):&#10;        for table in snapshot.tables:&#10;            self.operations.copy_database(&#10;                table.get_table_name('master'),&#10;                table.get_table_name('slave')&#10;            )&#10;        snapshot.worker_pid = None&#10;        self.db.session.commit()&#10;&#10;    def is_copy_process_running(self, snapshot):&#10;        return pid_exists(snapshot.worker_pid)&#10;&#10;    def is_old_database(self):&#10;        for snapshot in self.db.session.query(Snapshot):&#10;            for table in snapshot.tables:&#10;                for postfix in ('master', 'slave'):&#10;                    old_name = table.get_table_name(postfix=postfix, old=True)&#10;                    if self.operations.database_exists(old_name):&#10;                        return True&#10;        return False&#10;&#10;    def update_database_names_to_new_version(self, after_rename=None):&#10;        for snapshot in self.db.session.query(Snapshot):&#10;            for table in snapshot.tables:&#10;                for postfix in ('master', 'slave'):&#10;                    old_name = table.get_table_name(postfix=postfix, old=True)&#10;                    new_name = table.get_table_name(postfix=postfix, old=False)&#10;                    if self.operations.database_exists(old_name):&#10;                        self.operations.rename_database(old_name, new_name)&#10;                        if after_rename:&#10;                            after_rename(old_name, new_name)&#10;&#10;    def delete_orphan_snapshots(self, after_delete=None):&#10;        stellar_databases = set()&#10;        for snapshot in self.db.session.query(Snapshot):&#10;            for table in snapshot.tables:&#10;                stellar_databases.add(table.get_table_name('master'))&#10;                stellar_databases.add(table.get_table_name('slave'))&#10;&#10;        databases = set(self.operations.list_of_databases())&#10;&#10;        for database in filter(&#10;            lambda database: (&#10;                database.startswith('stellar_') and&#10;                database != 'stellar_data'&#10;            ),&#10;            (databases-stellar_databases)&#10;        ):&#10;            self.operations.remove_database(database)&#10;            if after_delete:&#10;                after_delete(database)&#10;&#10;    @property&#10;    def default_snapshot_name(self):&#10;        n = 1&#10;        while self.db.session.query(Snapshot).filter(&#10;            Snapshot.snapshot_name == 'snap%d' % n,&#10;            Snapshot.project_name == self.config['project_name']&#10;        ).count():&#10;            n += 1&#10;        return 'snap%d' % n&#10;"
    signature "None"
  ]
  node [
    id 3
    label "stellar.stellar.app.Operations"
    type "class"
    code "class Operations(object): def __init__(self, raw_connection, config): self.terminate_database_connections = partial( terminate_database_connections, raw_connection ) self.create_database = partial(create_database, raw_connection) self.copy_database = partial(copy_database, raw_connection) self.database_exists = partial(database_exists, raw_connection) self.rename_database = partial(rename_database, raw_connection) self.remove_database = partial(remove_database, raw_connection) self.list_of_databases = partial(list_of_databases, raw_connection)"
    signature "Operations"
  ]
  node [
    id 4
    label "stellar.stellar.app.Operations.__init__"
    type "function"
    code "def __init__(self, raw_connection, config): self.terminate_database_connections = partial( terminate_database_connections, raw_connection ) self.create_database = partial(create_database, raw_connection) self.copy_database = partial(copy_database, raw_connection) self.database_exists = partial(database_exists, raw_connection) self.rename_database = partial(rename_database, raw_connection) self.remove_database = partial(remove_database, raw_connection) self.list_of_databases = partial(list_of_databases, raw_connection)"
    signature "def __init__(self, raw_connection, config):"
  ]
  node [
    id 5
    label "stellar.stellar.app.Stellar"
    type "class"
    code "class Stellar(object): def __init__(self): logger.debug('Initialized Stellar()') self.load_config() self.init_database()  def load_config(self): self.config = load_config() logging.basicConfig(level=self.config['logging'])  def init_database(self): self.raw_db = create_engine(self.config['url'], echo=False) self.raw_conn = self.raw_db.connect() self.operations = Operations(self.raw_conn, self.config)  try: self.raw_conn.connection.set_isolation_level(0) except AttributeError: logger.info('Could not set isolation level to 0')  self.db = create_engine(self.config['stellar_url'], echo=False) self.db.session = sessionmaker(bind=self.db)() self.raw_db.session = sessionmaker(bind=self.raw_db)() tables_missing = self.create_stellar_database()  self.create_stellar_tables()  # logger.getLogger('sqlalchemy.engine').setLevel(logger.WARN)  def create_stellar_database(self): if not self.operations.database_exists('stellar_data'): self.operations.create_database('stellar_data') return True else: return False  def create_stellar_tables(self): Base.metadata.create_all(self.db) self.db.session.commit()  def get_snapshot(self, snapshot_name): return self.db.session.query(Snapshot).filter( Snapshot.snapshot_name == snapshot_name, Snapshot.project_name == self.config['project_name'] ).first()  def get_snapshots(self): return self.db.session.query(Snapshot).filter( Snapshot.project_name == self.config['project_name'] ).order_by( Snapshot.created_at.desc() ).all()  def get_latest_snapshot(self): return self.db.session.query(Snapshot).filter( Snapshot.project_name == self.config['project_name'] ).order_by(Snapshot.created_at.desc()).first()  def create_snapshot(self, snapshot_name, before_copy=None): snapshot = Snapshot( snapshot_name=snapshot_name, project_name=self.config['project_name'] ) self.db.session.add(snapshot) self.db.session.flush()  for table_name in self.config['tracked_databases']: if before_copy: before_copy(table_name) table = Table( table_name=table_name, snapshot=snapshot ) logger.debug('Copying %s to %s' % ( table_name, table.get_table_name('master') )) self.operations.copy_database( table_name, table.get_table_name('master') ) self.db.session.add(table) self.db.session.commit()  self.start_background_slave_copy(snapshot)  def remove_snapshot(self, snapshot): for table in snapshot.tables: try: self.operations.remove_database( table.get_table_name('master') ) except ProgrammingError: pass try: self.operations.remove_database( table.get_table_name('slave') ) except ProgrammingError: pass self.db.session.delete(table) self.db.session.delete(snapshot) self.db.session.commit()  def rename_snapshot(self, snapshot, new_name): snapshot.snapshot_name = new_name self.db.session.commit()  def restore(self, snapshot): for table in snapshot.tables: click.echo(&#34;Restoring database %s&#34; % table.table_name) if not self.operations.database_exists( table.get_table_name('slave') ): click.echo( &#34;Database %s does not exist.&#34; % table.get_table_name('slave') ) sys.exit(1) try: self.operations.remove_database(table.table_name) except ProgrammingError: logger.warn('Database %s does not exist.' % table.table_name) self.operations.rename_database( table.get_table_name('slave'), table.table_name ) snapshot.worker_pid = 1 self.db.session.commit()  self.start_background_slave_copy(snapshot)  def start_background_slave_copy(self, snapshot): logger.debug('Starting background slave copy') snapshot_id = snapshot.id  self.raw_conn.close() self.raw_db.session.close() self.db.session.close()  pid = os.fork() if hasattr(os, 'fork') else None if pid: return  self.init_database() self.operations = Operations(self.raw_conn, self.config)  snapshot = self.db.session.query(Snapshot).get(snapshot_id) snapshot.worker_pid = os.getpid() self.db.session.commit() self.inline_slave_copy(snapshot) sys.exit()  def inline_slave_copy(self, snapshot): for table in snapshot.tables: self.operations.copy_database( table.get_table_name('master'), table.get_table_name('slave') ) snapshot.worker_pid = None self.db.session.commit()  def is_copy_process_running(self, snapshot): return pid_exists(snapshot.worker_pid)  def is_old_database(self): for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: for postfix in ('master', 'slave'): old_name = table.get_table_name(postfix=postfix, old=True) if self.operations.database_exists(old_name): return True return False  def update_database_names_to_new_version(self, after_rename=None): for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: for postfix in ('master', 'slave'): old_name = table.get_table_name(postfix=postfix, old=True) new_name = table.get_table_name(postfix=postfix, old=False) if self.operations.database_exists(old_name): self.operations.rename_database(old_name, new_name) if after_rename: after_rename(old_name, new_name)  def delete_orphan_snapshots(self, after_delete=None): stellar_databases = set() for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: stellar_databases.add(table.get_table_name('master')) stellar_databases.add(table.get_table_name('slave'))  databases = set(self.operations.list_of_databases())  for database in filter( lambda database: ( database.startswith('stellar_') and database != 'stellar_data' ), (databases-stellar_databases) ): self.operations.remove_database(database) if after_delete: after_delete(database)  @property def default_snapshot_name(self): n = 1 while self.db.session.query(Snapshot).filter( Snapshot.snapshot_name == 'snap%d' % n, Snapshot.project_name == self.config['project_name'] ).count(): n += 1 return 'snap%d' % n"
    signature "Stellar"
  ]
  node [
    id 6
    label "stellar.stellar.app.Stellar.__init__"
    type "function"
    code "def __init__(self): logger.debug('Initialized Stellar()') self.load_config() self.init_database()"
    signature "def __init__(self):"
  ]
  node [
    id 7
    label "stellar.stellar.app.Stellar.load_config"
    type "function"
    code "def load_config(self): self.config = load_config() logging.basicConfig(level=self.config['logging'])"
    signature "def load_config(self):"
  ]
  node [
    id 8
    label "stellar.stellar.app.Stellar.init_database"
    type "function"
    code "def init_database(self): self.raw_db = create_engine(self.config['url'], echo=False) self.raw_conn = self.raw_db.connect() self.operations = Operations(self.raw_conn, self.config)  try: self.raw_conn.connection.set_isolation_level(0) except AttributeError: logger.info('Could not set isolation level to 0')  self.db = create_engine(self.config['stellar_url'], echo=False) self.db.session = sessionmaker(bind=self.db)() self.raw_db.session = sessionmaker(bind=self.raw_db)() tables_missing = self.create_stellar_database()  self.create_stellar_tables()  # logger.getLogger('sqlalchemy.engine').setLevel(logger.WARN)"
    signature "def init_database(self):"
  ]
  node [
    id 9
    label "stellar.stellar.app.Stellar.create_stellar_database"
    type "function"
    code "def create_stellar_database(self): if not self.operations.database_exists('stellar_data'): self.operations.create_database('stellar_data') return True else: return False"
    signature "def create_stellar_database(self):"
  ]
  node [
    id 10
    label "stellar.stellar.app.Stellar.create_stellar_tables"
    type "function"
    code "def create_stellar_tables(self): Base.metadata.create_all(self.db) self.db.session.commit()"
    signature "def create_stellar_tables(self):"
  ]
  node [
    id 11
    label "stellar.stellar.app.Stellar.get_snapshot"
    type "function"
    code "def get_snapshot(self, snapshot_name): return self.db.session.query(Snapshot).filter( Snapshot.snapshot_name == snapshot_name, Snapshot.project_name == self.config['project_name'] ).first()"
    signature "def get_snapshot(self, snapshot_name):"
  ]
  node [
    id 12
    label "stellar.stellar.app.Stellar.get_snapshots"
    type "function"
    code "def get_snapshots(self): return self.db.session.query(Snapshot).filter( Snapshot.project_name == self.config['project_name'] ).order_by( Snapshot.created_at.desc() ).all()"
    signature "def get_snapshots(self):"
  ]
  node [
    id 13
    label "stellar.stellar.app.Stellar.get_latest_snapshot"
    type "function"
    code "def get_latest_snapshot(self): return self.db.session.query(Snapshot).filter( Snapshot.project_name == self.config['project_name'] ).order_by(Snapshot.created_at.desc()).first()"
    signature "def get_latest_snapshot(self):"
  ]
  node [
    id 14
    label "stellar.stellar.app.Stellar.create_snapshot"
    type "function"
    code "def create_snapshot(self, snapshot_name, before_copy=None): snapshot = Snapshot( snapshot_name=snapshot_name, project_name=self.config['project_name'] ) self.db.session.add(snapshot) self.db.session.flush()  for table_name in self.config['tracked_databases']: if before_copy: before_copy(table_name) table = Table( table_name=table_name, snapshot=snapshot ) logger.debug('Copying %s to %s' % ( table_name, table.get_table_name('master') )) self.operations.copy_database( table_name, table.get_table_name('master') ) self.db.session.add(table) self.db.session.commit()  self.start_background_slave_copy(snapshot)"
    signature "def create_snapshot(self, snapshot_name, before_copy=None):"
  ]
  node [
    id 15
    label "stellar.stellar.app.Stellar.remove_snapshot"
    type "function"
    code "def remove_snapshot(self, snapshot): for table in snapshot.tables: try: self.operations.remove_database( table.get_table_name('master') ) except ProgrammingError: pass try: self.operations.remove_database( table.get_table_name('slave') ) except ProgrammingError: pass self.db.session.delete(table) self.db.session.delete(snapshot) self.db.session.commit()"
    signature "def remove_snapshot(self, snapshot):"
  ]
  node [
    id 16
    label "stellar.stellar.app.Stellar.rename_snapshot"
    type "function"
    code "def rename_snapshot(self, snapshot, new_name): snapshot.snapshot_name = new_name self.db.session.commit()"
    signature "def rename_snapshot(self, snapshot, new_name):"
  ]
  node [
    id 17
    label "stellar.stellar.app.Stellar.restore"
    type "function"
    code "def restore(self, snapshot): for table in snapshot.tables: click.echo(&#34;Restoring database %s&#34; % table.table_name) if not self.operations.database_exists( table.get_table_name('slave') ): click.echo( &#34;Database %s does not exist.&#34; % table.get_table_name('slave') ) sys.exit(1) try: self.operations.remove_database(table.table_name) except ProgrammingError: logger.warn('Database %s does not exist.' % table.table_name) self.operations.rename_database( table.get_table_name('slave'), table.table_name ) snapshot.worker_pid = 1 self.db.session.commit()  self.start_background_slave_copy(snapshot)"
    signature "def restore(self, snapshot):"
  ]
  node [
    id 18
    label "stellar.stellar.app.Stellar.start_background_slave_copy"
    type "function"
    code "def start_background_slave_copy(self, snapshot): logger.debug('Starting background slave copy') snapshot_id = snapshot.id  self.raw_conn.close() self.raw_db.session.close() self.db.session.close()  pid = os.fork() if hasattr(os, 'fork') else None if pid: return  self.init_database() self.operations = Operations(self.raw_conn, self.config)  snapshot = self.db.session.query(Snapshot).get(snapshot_id) snapshot.worker_pid = os.getpid() self.db.session.commit() self.inline_slave_copy(snapshot) sys.exit()"
    signature "def start_background_slave_copy(self, snapshot):"
  ]
  node [
    id 19
    label "stellar.stellar.app.Stellar.inline_slave_copy"
    type "function"
    code "def inline_slave_copy(self, snapshot): for table in snapshot.tables: self.operations.copy_database( table.get_table_name('master'), table.get_table_name('slave') ) snapshot.worker_pid = None self.db.session.commit()"
    signature "def inline_slave_copy(self, snapshot):"
  ]
  node [
    id 20
    label "stellar.stellar.app.Stellar.is_copy_process_running"
    type "function"
    code "def is_copy_process_running(self, snapshot): return pid_exists(snapshot.worker_pid)"
    signature "def is_copy_process_running(self, snapshot):"
  ]
  node [
    id 21
    label "stellar.stellar.app.Stellar.is_old_database"
    type "function"
    code "def is_old_database(self): for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: for postfix in ('master', 'slave'): old_name = table.get_table_name(postfix=postfix, old=True) if self.operations.database_exists(old_name): return True return False"
    signature "def is_old_database(self):"
  ]
  node [
    id 22
    label "stellar.stellar.app.Stellar.update_database_names_to_new_version"
    type "function"
    code "def update_database_names_to_new_version(self, after_rename=None): for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: for postfix in ('master', 'slave'): old_name = table.get_table_name(postfix=postfix, old=True) new_name = table.get_table_name(postfix=postfix, old=False) if self.operations.database_exists(old_name): self.operations.rename_database(old_name, new_name) if after_rename: after_rename(old_name, new_name)"
    signature "def update_database_names_to_new_version(self, after_rename=None):"
  ]
  node [
    id 23
    label "stellar.stellar.app.Stellar.delete_orphan_snapshots"
    type "function"
    code "def delete_orphan_snapshots(self, after_delete=None): stellar_databases = set() for snapshot in self.db.session.query(Snapshot): for table in snapshot.tables: stellar_databases.add(table.get_table_name('master')) stellar_databases.add(table.get_table_name('slave'))  databases = set(self.operations.list_of_databases())  for database in filter( lambda database: ( database.startswith('stellar_') and database != 'stellar_data' ), (databases-stellar_databases) ): self.operations.remove_database(database) if after_delete: after_delete(database)"
    signature "def delete_orphan_snapshots(self, after_delete=None):"
  ]
  node [
    id 24
    label "stellar.stellar.app.Stellar.default_snapshot_name"
    type "function"
    code "def default_snapshot_name(self): n = 1 while self.db.session.query(Snapshot).filter( Snapshot.snapshot_name == 'snap%d' % n, Snapshot.project_name == self.config['project_name'] ).count(): n += 1 return 'snap%d' % n"
    signature "def default_snapshot_name(self):"
  ]
  node [
    id 25
    label "stellar.stellar.config"
    type "module"
    code "import os&#10;import logging&#10;import yaml&#10;from schema import Use, Schema, SchemaError, Optional&#10;&#10;&#10;class InvalidConfig(Exception):&#10;    pass&#10;&#10;&#10;class MissingConfig(Exception):&#10;    pass&#10;&#10;&#10;default_config = {&#10;    'logging': 30,&#10;    'migrate_from_0_3_2': True&#10;}&#10;schema = Schema({&#10;    'stellar_url': Use(str),&#10;    'url': Use(str),&#10;    'project_name': Use(str),&#10;    'tracked_databases': [Use(str)],&#10;    Optional('logging'): int,&#10;    Optional('migrate_from_0_3_2'): bool&#10;})&#10;&#10;&#10;def get_config_path():&#10;    current_directory = os.getcwd()&#10;    while True:&#10;        try:&#10;            with open(&#10;                os.path.join(current_directory, 'stellar.yaml'),&#10;                'rb'&#10;            ) as fp:&#10;                return os.path.join(current_directory, 'stellar.yaml')&#10;        except IOError:&#10;            pass&#10;&#10;        current_directory = os.path.abspath(&#10;            os.path.join(current_directory, '..')&#10;        )&#10;        if current_directory == '/':&#10;            return None&#10;&#10;&#10;def load_config():&#10;    config = {}&#10;    current_directory = os.getcwd()&#10;    while True:&#10;        try:&#10;            with open(&#10;                os.path.join(current_directory, 'stellar.yaml'),&#10;                'rb'&#10;            ) as fp:&#10;                config = yaml.safe_load(fp)&#10;                break&#10;        except IOError:&#10;            pass&#10;        current_directory = os.path.abspath(&#10;            os.path.join(current_directory, '..')&#10;        )&#10;&#10;        if current_directory == '/':&#10;            break&#10;&#10;    if not config:&#10;        raise MissingConfig()&#10;&#10;    for k, v in default_config.items():&#10;        if k not in config:&#10;            config[k] = v&#10;&#10;    try:&#10;        return schema.validate(config)&#10;    except SchemaError as e:&#10;        raise InvalidConfig(e)&#10;&#10;&#10;def save_config(config):&#10;    logging.getLogger(__name__).debug('save_config()')&#10;    with open(get_config_path(), &#34;w&#34;) as fp:&#10;        yaml.dump(config, fp)&#10;"
    signature "None"
  ]
  node [
    id 26
    label "stellar.stellar.config.InvalidConfig"
    type "class"
    code "class InvalidConfig(Exception): pass"
    signature "InvalidConfig"
  ]
  node [
    id 27
    label "stellar.stellar.config.MissingConfig"
    type "class"
    code "class MissingConfig(Exception): pass"
    signature "MissingConfig"
  ]
  node [
    id 28
    label "stellar.stellar.config.get_config_path"
    type "function"
    code "def get_config_path(): current_directory = os.getcwd() while True: try: with open( os.path.join(current_directory, 'stellar.yaml'), 'rb' ) as fp: return os.path.join(current_directory, 'stellar.yaml') except IOError: pass  current_directory = os.path.abspath( os.path.join(current_directory, '..') ) if current_directory == '/': return None"
    signature "def get_config_path():"
  ]
  node [
    id 29
    label "stellar.stellar.config.load_config"
    type "function"
    code "def load_config(): config = {} current_directory = os.getcwd() while True: try: with open( os.path.join(current_directory, 'stellar.yaml'), 'rb' ) as fp: config = yaml.safe_load(fp) break except IOError: pass current_directory = os.path.abspath( os.path.join(current_directory, '..') )  if current_directory == '/': break  if not config: raise MissingConfig()  for k, v in default_config.items(): if k not in config: config[k] = v  try: return schema.validate(config) except SchemaError as e: raise InvalidConfig(e)"
    signature "def load_config():"
  ]
  node [
    id 30
    label "stellar.stellar.config.save_config"
    type "function"
    code "def save_config(config): logging.getLogger(__name__).debug('save_config()') with open(get_config_path(), &#34;w&#34;) as fp: yaml.dump(config, fp)"
    signature "def save_config(config):"
  ]
  node [
    id 31
    label "stellar.stellar.models"
    type "module"
    code "import hashlib&#10;import uuid&#10;from datetime import datetime&#10;&#10;import sqlalchemy as sa&#10;from sqlalchemy.ext.declarative import declarative_base&#10;&#10;Base = declarative_base()&#10;&#10;&#10;def get_unique_hash():&#10;    return hashlib.md5(str(uuid.uuid4()).encode('utf-8')).hexdigest()&#10;&#10;&#10;class Snapshot(Base):&#10;    __tablename__ = 'snapshot'&#10;    id = sa.Column(&#10;        sa.Integer,&#10;        sa.Sequence('snapshot_id_seq'),&#10;        primary_key=True&#10;    )&#10;    snapshot_name = sa.Column(sa.String(255), nullable=False)&#10;    project_name = sa.Column(sa.String(255), nullable=False)&#10;    hash = sa.Column(sa.String(32), nullable=False, default=get_unique_hash)&#10;    created_at = sa.Column(sa.DateTime, default=datetime.utcnow)&#10;    worker_pid = sa.Column(sa.Integer, nullable=True)&#10;&#10;    @property&#10;    def slaves_ready(self):&#10;        return self.worker_pid is None&#10;&#10;    def __repr__(self):&#10;        return &#34;<Snapshot(snapshot_name=%r)>&#34; % (&#10;            self.snapshot_name&#10;        )&#10;&#10;&#10;class Table(Base):&#10;    __tablename__ = 'table'&#10;    id = sa.Column(sa.Integer, sa.Sequence('table_id_seq'), primary_key=True)&#10;    table_name = sa.Column(sa.String(255), nullable=False)&#10;    snapshot_id = sa.Column(&#10;        sa.Integer, sa.ForeignKey(Snapshot.id), nullable=False&#10;    )&#10;    snapshot = sa.orm.relationship(Snapshot, backref='tables')&#10;&#10;    def get_table_name(self, postfix, old=False):&#10;        if not self.snapshot:&#10;            raise Exception('Table name requires snapshot')&#10;        if not self.snapshot.hash:&#10;            raise Exception('Snapshot hash is empty.')&#10;&#10;        if old:&#10;            return 'stellar_%s_%s_%s' % (&#10;                self.table_name,&#10;                self.snapshot.hash,&#10;                postfix&#10;            )&#10;        else:&#10;            return 'stellar_%s' % hashlib.md5(&#10;                ('%s|%s|%s' % (&#10;                    self.table_name,&#10;                    self.snapshot.hash,&#10;                    postfix&#10;                )).encode('utf-8')&#10;            ).hexdigest()[0:16]&#10;&#10;    def __repr__(self):&#10;        return &#34;<Table(table_name=%r)>&#34; % (&#10;            self.table_name,&#10;        )&#10;"
    signature "None"
  ]
  node [
    id 32
    label "stellar.stellar.models.get_unique_hash"
    type "function"
    code "def get_unique_hash(): return hashlib.md5(str(uuid.uuid4()).encode('utf-8')).hexdigest()"
    signature "def get_unique_hash():"
  ]
  node [
    id 33
    label "stellar.stellar.models.Snapshot"
    type "class"
    code "class Snapshot(Base): __tablename__ = 'snapshot' id = sa.Column( sa.Integer, sa.Sequence('snapshot_id_seq'), primary_key=True ) snapshot_name = sa.Column(sa.String(255), nullable=False) project_name = sa.Column(sa.String(255), nullable=False) hash = sa.Column(sa.String(32), nullable=False, default=get_unique_hash) created_at = sa.Column(sa.DateTime, default=datetime.utcnow) worker_pid = sa.Column(sa.Integer, nullable=True)  @property def slaves_ready(self): return self.worker_pid is None  def __repr__(self): return &#34;<Snapshot(snapshot_name=%r)>&#34; % ( self.snapshot_name )"
    signature "Snapshot"
  ]
  node [
    id 34
    label "stellar.stellar.models.Snapshot.slaves_ready"
    type "function"
    code "def slaves_ready(self): return self.worker_pid is None"
    signature "def slaves_ready(self):"
  ]
  node [
    id 35
    label "stellar.stellar.models.Snapshot.__repr__"
    type "function"
    code "def __repr__(self): return &#34;<Snapshot(snapshot_name=%r)>&#34; % ( self.snapshot_name )"
    signature "def __repr__(self):"
  ]
  node [
    id 36
    label "stellar.stellar.models.Table"
    type "class"
    code "class Table(Base): __tablename__ = 'table' id = sa.Column(sa.Integer, sa.Sequence('table_id_seq'), primary_key=True) table_name = sa.Column(sa.String(255), nullable=False) snapshot_id = sa.Column( sa.Integer, sa.ForeignKey(Snapshot.id), nullable=False ) snapshot = sa.orm.relationship(Snapshot, backref='tables')  def get_table_name(self, postfix, old=False): if not self.snapshot: raise Exception('Table name requires snapshot') if not self.snapshot.hash: raise Exception('Snapshot hash is empty.')  if old: return 'stellar_%s_%s_%s' % ( self.table_name, self.snapshot.hash, postfix ) else: return 'stellar_%s' % hashlib.md5( ('%s|%s|%s' % ( self.table_name, self.snapshot.hash, postfix )).encode('utf-8') ).hexdigest()[0:16]  def __repr__(self): return &#34;<Table(table_name=%r)>&#34; % ( self.table_name, )"
    signature "Table"
  ]
  node [
    id 37
    label "stellar.stellar.models.Table.get_table_name"
    type "function"
    code "def get_table_name(self, postfix, old=False): if not self.snapshot: raise Exception('Table name requires snapshot') if not self.snapshot.hash: raise Exception('Snapshot hash is empty.')  if old: return 'stellar_%s_%s_%s' % ( self.table_name, self.snapshot.hash, postfix ) else: return 'stellar_%s' % hashlib.md5( ('%s|%s|%s' % ( self.table_name, self.snapshot.hash, postfix )).encode('utf-8') ).hexdigest()[0:16]"
    signature "def get_table_name(self, postfix, old=False):"
  ]
  node [
    id 38
    label "stellar.stellar.models.Table.__repr__"
    type "function"
    code "def __repr__(self): return &#34;<Table(table_name=%r)>&#34; % ( self.table_name, )"
    signature "def __repr__(self):"
  ]
  node [
    id 39
    label "stellar.stellar.__main__"
    type "module"
    code "from .command import main&#10;&#10;main()&#10;"
    signature "None"
  ]
  node [
    id 40
    label "stellar.stellar.command"
    type "module"
    code "import sys&#10;from datetime import datetime&#10;from time import sleep&#10;&#10;import humanize&#10;import click&#10;import logging&#10;from sqlalchemy import create_engine&#10;from sqlalchemy.exc import OperationalError&#10;&#10;from .app import Stellar, __version__&#10;from .config import InvalidConfig, MissingConfig, load_config, save_config&#10;from .operations import database_exists, list_of_databases, SUPPORTED_DIALECTS&#10;&#10;&#10;def upgrade_from_old_version(app):&#10;    if app.config['migrate_from_0_3_2']:&#10;        if app.is_old_database():&#10;            click.echo('Upgrading from old Stellar version...')&#10;            def after_rename(old_name, new_name):&#10;                click.echo('* Renamed %s to %s' % (old_name, new_name))&#10;            app.update_database_names_to_new_version(after_rename=after_rename)&#10;&#10;        app.config['migrate_from_0_3_2'] = False&#10;        save_config(app.config)&#10;&#10;def get_app():&#10;    app = Stellar()&#10;    upgrade_from_old_version(app)&#10;    return app&#10;&#10;&#10;@click.group()&#10;def stellar():&#10;    &#34;&#34;&#34;Fast database snapshots for development. It's like Git for databases.&#34;&#34;&#34;&#10;    pass&#10;&#10;&#10;@stellar.command()&#10;def version():&#10;    &#34;&#34;&#34;Shows version number&#34;&#34;&#34;&#10;    click.echo(&#34;Stellar %s&#34; % __version__)&#10;&#10;&#10;@stellar.command()&#10;def gc():&#10;    &#34;&#34;&#34;Deletes old stellar tables that are not used anymore&#34;&#34;&#34;&#10;    def after_delete(database):&#10;        click.echo(&#34;Deleted table %s&#34; % database)&#10;&#10;    app = get_app()&#10;    upgrade_from_old_version(app)&#10;    app.delete_orphan_snapshots(after_delete)&#10;&#10;&#10;@stellar.command()&#10;@click.argument('name', required=False)&#10;def snapshot(name):&#10;    &#34;&#34;&#34;Takes a snapshot of the database&#34;&#34;&#34;&#10;    app = get_app()&#10;    upgrade_from_old_version(app)&#10;    name = name or app.default_snapshot_name&#10;&#10;    if app.get_snapshot(name):&#10;        click.echo(&#34;Snapshot with name %s already exists&#34; % name)&#10;        sys.exit(1)&#10;    else:&#10;        def before_copy(table_name):&#10;            click.echo(&#34;Snapshotting database %s&#34; % table_name)&#10;        app.create_snapshot(name, before_copy=before_copy)&#10;&#10;&#10;@stellar.command()&#10;def list():&#10;    &#34;&#34;&#34;Returns a list of snapshots&#34;&#34;&#34;&#10;    snapshots = get_app().get_snapshots()&#10;&#10;    click.echo('\n'.join(&#10;        '%s: %s' % (&#10;            s.snapshot_name,&#10;            humanize.naturaltime(datetime.utcnow() - s.created_at)&#10;        )&#10;        for s in snapshots&#10;    ))&#10;&#10;&#10;@stellar.command()&#10;@click.argument('name', required=False)&#10;def restore(name):&#10;    &#34;&#34;&#34;Restores the database from a snapshot&#34;&#34;&#34;&#10;    app = get_app()&#10;&#10;    if not name:&#10;        snapshot = app.get_latest_snapshot()&#10;        if not snapshot:&#10;            click.echo(&#10;                &#34;Couldn't find any snapshots for project %s&#34; %&#10;                load_config()['project_name']&#10;            )&#10;            sys.exit(1)&#10;    else:&#10;        snapshot = app.get_snapshot(name)&#10;        if not snapshot:&#10;            click.echo(&#10;                &#34;Couldn't find snapshot with name %s.\n&#34;&#10;                &#34;You can list snapshots with 'stellar list'&#34; % name&#10;            )&#10;            sys.exit(1)&#10;&#10;    # Check if slaves are ready&#10;    if not snapshot.slaves_ready:&#10;        if app.is_copy_process_running(snapshot):&#10;            sys.stdout.write(&#10;                'Waiting for background process(%s) to finish' %&#10;                snapshot.worker_pid&#10;            )&#10;            sys.stdout.flush()&#10;            while not snapshot.slaves_ready:&#10;                sys.stdout.write('.')&#10;                sys.stdout.flush()&#10;                sleep(1)&#10;                app.db.session.refresh(snapshot)&#10;            click.echo('')&#10;        else:&#10;            click.echo('Background process missing, doing slow restore.')&#10;            app.inline_slave_copy(snapshot)&#10;&#10;    app.restore(snapshot)&#10;    click.echo('Restore complete.')&#10;&#10;&#10;@stellar.command()&#10;@click.argument('name')&#10;def remove(name):&#10;    &#34;&#34;&#34;Removes a snapshot&#34;&#34;&#34;&#10;    app = get_app()&#10;&#10;    snapshot = app.get_snapshot(name)&#10;    if not snapshot:&#10;        click.echo(&#34;Couldn't find snapshot %s&#34; % name)&#10;        sys.exit(1)&#10;&#10;    click.echo(&#34;Deleting snapshot %s&#34; % name)&#10;    app.remove_snapshot(snapshot)&#10;    click.echo(&#34;Deleted&#34;)&#10;&#10;&#10;@stellar.command()&#10;@click.argument('old_name')&#10;@click.argument('new_name')&#10;def rename(old_name, new_name):&#10;    &#34;&#34;&#34;Renames a snapshot&#34;&#34;&#34;&#10;    app = get_app()&#10;&#10;    snapshot = app.get_snapshot(old_name)&#10;    if not snapshot:&#10;        click.echo(&#34;Couldn't find snapshot %s&#34; % old_name)&#10;        sys.exit(1)&#10;&#10;    new_snapshot = app.get_snapshot(new_name)&#10;    if new_snapshot:&#10;        click.echo(&#34;Snapshot with name %s already exists&#34; % new_name)&#10;        sys.exit(1)&#10;&#10;    app.rename_snapshot(snapshot, new_name)&#10;    click.echo(&#34;Renamed snapshot %s to %s&#34; % (old_name, new_name))&#10;&#10;&#10;@stellar.command()&#10;@click.argument('name')&#10;def replace(name):&#10;    &#34;&#34;&#34;Replaces a snapshot&#34;&#34;&#34;&#10;    app = get_app()&#10;&#10;    snapshot = app.get_snapshot(name)&#10;    if not snapshot:&#10;        click.echo(&#34;Couldn't find snapshot %s&#34; % name)&#10;        sys.exit(1)&#10;&#10;    app.remove_snapshot(snapshot)&#10;    app.create_snapshot(name)&#10;    click.echo(&#34;Replaced snapshot %s&#34; % name)&#10;&#10;&#10;@stellar.command()&#10;def init():&#10;    &#34;&#34;&#34;Initializes Stellar configuration.&#34;&#34;&#34;&#10;    while True:&#10;        url = click.prompt(&#10;            &#34;Please enter the url for your database.\n\n&#34;&#10;            &#34;For example:\n&#34;&#10;            &#34;PostgreSQL: postgresql://localhost:5432/\n&#34;&#10;            &#34;MySQL: mysql+pymysql://root@localhost/&#34;&#10;        )&#10;        if url.count('/') == 2 and not url.endswith('/'):&#10;            url = url + '/'&#10;&#10;        if (&#10;            url.count('/') == 3 and&#10;            url.endswith('/') and&#10;            url.startswith('postgresql://')&#10;        ):&#10;            connection_url = url + 'template1'&#10;        else:&#10;            connection_url = url&#10;&#10;        engine = create_engine(connection_url, echo=False)&#10;        try:&#10;            conn = engine.connect()&#10;        except OperationalError as err:&#10;            click.echo(&#34;Could not connect to database: %s&#34; % url)&#10;            click.echo(&#34;Error message: %s&#34; % err.message)&#10;            click.echo('')&#10;        else:&#10;            break&#10;&#10;    if engine.dialect.name not in SUPPORTED_DIALECTS:&#10;        click.echo(&#34;Your engine dialect %s is not supported.&#34; % (&#10;            engine.dialect.name&#10;        ))&#10;        click.echo(&#34;Supported dialects: %s&#34; % (&#10;            ', '.join(SUPPORTED_DIALECTS)&#10;        ))&#10;&#10;    if url.count('/') == 3 and url.endswith('/'):&#10;        while True:&#10;            click.echo(&#34;You have the following databases: %s&#34; % ', '.join([&#10;                db for db in list_of_databases(conn)&#10;                if not db.startswith('stellar_')&#10;            ]))&#10;&#10;            db_name = click.prompt(&#10;                &#34;Please enter the name of the database (eg. projectdb)&#34;&#10;            )&#10;            if database_exists(conn, db_name):&#10;                break&#10;            else:&#10;                click.echo(&#34;Could not find database %s&#34; % db_name)&#10;                click.echo('')&#10;    else:&#10;        db_name = url.rsplit('/', 1)[-1]&#10;        url = url.rsplit('/', 1)[0] + '/'&#10;&#10;    name = click.prompt(&#10;        'Please enter your project name (used internally, eg. %s)' % db_name,&#10;        default=db_name&#10;    )&#10;&#10;    raw_url = url&#10;&#10;    if engine.dialect.name == 'postgresql':&#10;        raw_url = raw_url + 'template1'&#10;&#10;    with open('stellar.yaml', 'w') as project_file:&#10;        project_file.write(&#10;            &#34;&#34;&#34;&#10;project_name: '%(name)s'&#10;tracked_databases: ['%(db_name)s']&#10;url: '%(raw_url)s'&#10;stellar_url: '%(url)sstellar_data'&#10;            &#34;&#34;&#34;.strip() %&#10;            {&#10;                'name': name,&#10;                'raw_url': raw_url,&#10;                'url': url,&#10;                'db_name': db_name&#10;            }&#10;        )&#10;&#10;    click.echo(&#34;Wrote stellar.yaml&#34;)&#10;    click.echo('')&#10;    if engine.dialect.name == 'mysql':&#10;        click.echo(&#34;Warning: MySQL support is still in beta.&#34;)&#10;    click.echo(&#34;Tip: You probably want to take a snapshot: stellar snapshot&#34;)&#10;&#10;&#10;def main():&#10;    try:&#10;        stellar()&#10;    except MissingConfig:&#10;        click.echo(&#34;You don't have stellar.yaml configuration yet.&#34;)&#10;        click.echo(&#34;Initialize it by running: stellar init&#34;)&#10;        sys.exit(1)&#10;    except InvalidConfig as e:&#10;        click.echo(&#34;Your stellar.yaml configuration is wrong: %s&#34; % e.message)&#10;        sys.exit(1)&#10;    except ImportError as e:&#10;        libraries = {&#10;            'psycopg2': 'PostreSQL',&#10;            'pymysql': 'MySQL',&#10;        }&#10;        for library, name in libraries.items():&#10;            if 'No module named' in str(e) and library in str(e):&#10;                click.echo(&#10;                    &#34;Python library %s is required for %s support.&#34; %&#10;                    (library, name)&#10;                )&#10;                click.echo(&#34;You can install it with pip:&#34;)&#10;                click.echo(&#34;pip install %s&#34; % library)&#10;                sys.exit(1)&#10;            elif 'No module named' in str(e) and 'MySQLdb' in str(e):&#10;                click.echo(&#10;                    &#34;MySQLdb binary drivers are required for MySQL support. &#34;&#10;                    &#34;You can try installing it with these instructions: &#34;&#10;                    &#34;http://stackoverflow.com/questions/454854/no-module-named&#34;&#10;                    &#34;-mysqldb&#34;&#10;                )&#10;                click.echo('')&#10;                click.echo(&#34;Alternatively you can use pymysql instead:&#34;)&#10;                click.echo(&#34;1. Install it first: pip install pymysql&#34;)&#10;                click.echo(&#10;                    &#34;2. Specify database url as &#34;&#10;                    &#34;mysql+pymysql://root@localhost/ and not as &#34;&#10;                    &#34;mysql://root@localhost/&#34;&#10;                )&#10;                sys.exit(1)&#10;        raise&#10;&#10;if __name__ == '__main__':&#10;    main()&#10;"
    signature "None"
  ]
  node [
    id 41
    label "stellar.stellar.command.upgrade_from_old_version"
    type "function"
    code "def upgrade_from_old_version(app): if app.config['migrate_from_0_3_2']: if app.is_old_database(): click.echo('Upgrading from old Stellar version...') def after_rename(old_name, new_name): click.echo('* Renamed %s to %s' % (old_name, new_name)) app.update_database_names_to_new_version(after_rename=after_rename)  app.config['migrate_from_0_3_2'] = False save_config(app.config)"
    signature "def upgrade_from_old_version(app):"
  ]
  node [
    id 42
    label "stellar.stellar.command.upgrade_from_old_version.after_rename"
    type "function"
    code "def after_rename(old_name, new_name): click.echo('* Renamed %s to %s' % (old_name, new_name))"
    signature "def after_rename(old_name, new_name):"
  ]
  node [
    id 43
    label "stellar.stellar.command.get_app"
    type "function"
    code "def get_app(): app = Stellar() upgrade_from_old_version(app) return app"
    signature "def get_app():"
  ]
  node [
    id 44
    label "stellar.stellar.command.stellar"
    type "function"
    code "def stellar(): &#34;&#34;&#34;Fast database snapshots for development. It's like Git for databases.&#34;&#34;&#34; pass"
    signature "def stellar():"
  ]
  node [
    id 45
    label "stellar.stellar.command.version"
    type "function"
    code "def version(): &#34;&#34;&#34;Shows version number&#34;&#34;&#34; click.echo(&#34;Stellar %s&#34; % __version__)"
    signature "def version():"
  ]
  node [
    id 46
    label "stellar.stellar.command.gc"
    type "function"
    code "def gc(): &#34;&#34;&#34;Deletes old stellar tables that are not used anymore&#34;&#34;&#34; def after_delete(database): click.echo(&#34;Deleted table %s&#34; % database)  app = get_app() upgrade_from_old_version(app) app.delete_orphan_snapshots(after_delete)"
    signature "def gc():"
  ]
  node [
    id 47
    label "stellar.stellar.command.gc.after_delete"
    type "function"
    code "def after_delete(database): click.echo(&#34;Deleted table %s&#34; % database)"
    signature "def after_delete(database):"
  ]
  node [
    id 48
    label "stellar.stellar.command.snapshot"
    type "function"
    code "def snapshot(name): &#34;&#34;&#34;Takes a snapshot of the database&#34;&#34;&#34; app = get_app() upgrade_from_old_version(app) name = name or app.default_snapshot_name  if app.get_snapshot(name): click.echo(&#34;Snapshot with name %s already exists&#34; % name) sys.exit(1) else: def before_copy(table_name): click.echo(&#34;Snapshotting database %s&#34; % table_name) app.create_snapshot(name, before_copy=before_copy)"
    signature "def snapshot(name):"
  ]
  node [
    id 49
    label "stellar.stellar.command.snapshot.before_copy"
    type "function"
    code "def before_copy(table_name): click.echo(&#34;Snapshotting database %s&#34; % table_name)"
    signature "def before_copy(table_name):"
  ]
  node [
    id 50
    label "stellar.stellar.command.list"
    type "function"
    code "def list(): &#34;&#34;&#34;Returns a list of snapshots&#34;&#34;&#34; snapshots = get_app().get_snapshots()  click.echo('\n'.join( '%s: %s' % ( s.snapshot_name, humanize.naturaltime(datetime.utcnow() - s.created_at) ) for s in snapshots ))"
    signature "def list():"
  ]
  node [
    id 51
    label "stellar.stellar.command.restore"
    type "function"
    code "def restore(name): &#34;&#34;&#34;Restores the database from a snapshot&#34;&#34;&#34; app = get_app()  if not name: snapshot = app.get_latest_snapshot() if not snapshot: click.echo( &#34;Couldn't find any snapshots for project %s&#34; % load_config()['project_name'] ) sys.exit(1) else: snapshot = app.get_snapshot(name) if not snapshot: click.echo( &#34;Couldn't find snapshot with name %s.\n&#34; &#34;You can list snapshots with 'stellar list'&#34; % name ) sys.exit(1)  # Check if slaves are ready if not snapshot.slaves_ready: if app.is_copy_process_running(snapshot): sys.stdout.write( 'Waiting for background process(%s) to finish' % snapshot.worker_pid ) sys.stdout.flush() while not snapshot.slaves_ready: sys.stdout.write('.') sys.stdout.flush() sleep(1) app.db.session.refresh(snapshot) click.echo('') else: click.echo('Background process missing, doing slow restore.') app.inline_slave_copy(snapshot)  app.restore(snapshot) click.echo('Restore complete.')"
    signature "def restore(name):"
  ]
  node [
    id 52
    label "stellar.stellar.command.remove"
    type "function"
    code "def remove(name): &#34;&#34;&#34;Removes a snapshot&#34;&#34;&#34; app = get_app()  snapshot = app.get_snapshot(name) if not snapshot: click.echo(&#34;Couldn't find snapshot %s&#34; % name) sys.exit(1)  click.echo(&#34;Deleting snapshot %s&#34; % name) app.remove_snapshot(snapshot) click.echo(&#34;Deleted&#34;)"
    signature "def remove(name):"
  ]
  node [
    id 53
    label "stellar.stellar.command.rename"
    type "function"
    code "def rename(old_name, new_name): &#34;&#34;&#34;Renames a snapshot&#34;&#34;&#34; app = get_app()  snapshot = app.get_snapshot(old_name) if not snapshot: click.echo(&#34;Couldn't find snapshot %s&#34; % old_name) sys.exit(1)  new_snapshot = app.get_snapshot(new_name) if new_snapshot: click.echo(&#34;Snapshot with name %s already exists&#34; % new_name) sys.exit(1)  app.rename_snapshot(snapshot, new_name) click.echo(&#34;Renamed snapshot %s to %s&#34; % (old_name, new_name))"
    signature "def rename(old_name, new_name):"
  ]
  node [
    id 54
    label "stellar.stellar.command.replace"
    type "function"
    code "def replace(name): &#34;&#34;&#34;Replaces a snapshot&#34;&#34;&#34; app = get_app()  snapshot = app.get_snapshot(name) if not snapshot: click.echo(&#34;Couldn't find snapshot %s&#34; % name) sys.exit(1)  app.remove_snapshot(snapshot) app.create_snapshot(name) click.echo(&#34;Replaced snapshot %s&#34; % name)"
    signature "def replace(name):"
  ]
  node [
    id 55
    label "stellar.stellar.command.init"
    type "function"
    code "def init(): &#34;&#34;&#34;Initializes Stellar configuration.&#34;&#34;&#34; while True: url = click.prompt( &#34;Please enter the url for your database.\n\n&#34; &#34;For example:\n&#34; &#34;PostgreSQL: postgresql://localhost:5432/\n&#34; &#34;MySQL: mysql+pymysql://root@localhost/&#34; ) if url.count('/') == 2 and not url.endswith('/'): url = url + '/'  if ( url.count('/') == 3 and url.endswith('/') and url.startswith('postgresql://') ): connection_url = url + 'template1' else: connection_url = url  engine = create_engine(connection_url, echo=False) try: conn = engine.connect() except OperationalError as err: click.echo(&#34;Could not connect to database: %s&#34; % url) click.echo(&#34;Error message: %s&#34; % err.message) click.echo('') else: break  if engine.dialect.name not in SUPPORTED_DIALECTS: click.echo(&#34;Your engine dialect %s is not supported.&#34; % ( engine.dialect.name )) click.echo(&#34;Supported dialects: %s&#34; % ( ', '.join(SUPPORTED_DIALECTS) ))  if url.count('/') == 3 and url.endswith('/'): while True: click.echo(&#34;You have the following databases: %s&#34; % ', '.join([ db for db in list_of_databases(conn) if not db.startswith('stellar_') ]))  db_name = click.prompt( &#34;Please enter the name of the database (eg. projectdb)&#34; ) if database_exists(conn, db_name): break else: click.echo(&#34;Could not find database %s&#34; % db_name) click.echo('') else: db_name = url.rsplit('/', 1)[-1] url = url.rsplit('/', 1)[0] + '/'  name = click.prompt( 'Please enter your project name (used internally, eg. %s)' % db_name, default=db_name )  raw_url = url  if engine.dialect.name == 'postgresql': raw_url = raw_url + 'template1'  with open('stellar.yaml', 'w') as project_file: project_file.write( &#34;&#34;&#34; project_name: '%(name)s' tracked_databases: ['%(db_name)s'] url: '%(raw_url)s' stellar_url: '%(url)sstellar_data' &#34;&#34;&#34;.strip() % { 'name': name, 'raw_url': raw_url, 'url': url, 'db_name': db_name } )  click.echo(&#34;Wrote stellar.yaml&#34;) click.echo('') if engine.dialect.name == 'mysql': click.echo(&#34;Warning: MySQL support is still in beta.&#34;) click.echo(&#34;Tip: You probably want to take a snapshot: stellar snapshot&#34;)"
    signature "def init():"
  ]
  node [
    id 56
    label "stellar.stellar.command.main"
    type "function"
    code "def main(): try: stellar() except MissingConfig: click.echo(&#34;You don't have stellar.yaml configuration yet.&#34;) click.echo(&#34;Initialize it by running: stellar init&#34;) sys.exit(1) except InvalidConfig as e: click.echo(&#34;Your stellar.yaml configuration is wrong: %s&#34; % e.message) sys.exit(1) except ImportError as e: libraries = { 'psycopg2': 'PostreSQL', 'pymysql': 'MySQL', } for library, name in libraries.items(): if 'No module named' in str(e) and library in str(e): click.echo( &#34;Python library %s is required for %s support.&#34; % (library, name) ) click.echo(&#34;You can install it with pip:&#34;) click.echo(&#34;pip install %s&#34; % library) sys.exit(1) elif 'No module named' in str(e) and 'MySQLdb' in str(e): click.echo( &#34;MySQLdb binary drivers are required for MySQL support. &#34; &#34;You can try installing it with these instructions: &#34; &#34;http://stackoverflow.com/questions/454854/no-module-named&#34; &#34;-mysqldb&#34; ) click.echo('') click.echo(&#34;Alternatively you can use pymysql instead:&#34;) click.echo(&#34;1. Install it first: pip install pymysql&#34;) click.echo( &#34;2. Specify database url as &#34; &#34;mysql+pymysql://root@localhost/ and not as &#34; &#34;mysql://root@localhost/&#34; ) sys.exit(1) raise"
    signature "def main():"
  ]
  node [
    id 57
    label "stellar.stellar.__pycache__"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 58
    label "stellar.stellar.operations"
    type "module"
    code "import logging&#10;import re&#10;&#10;import sqlalchemy_utils&#10;&#10;logger = logging.getLogger(__name__)&#10;&#10;&#10;SUPPORTED_DIALECTS = (&#10;    'postgresql',&#10;    'mysql'&#10;)&#10;&#10;class NotSupportedDatabase(Exception):&#10;    pass&#10;&#10;&#10;def get_engine_url(raw_conn, database):&#10;    url = str(raw_conn.engine.url)&#10;    if url.count('/') == 3 and url.endswith('/'):&#10;        return '%s%s' % (url, database)&#10;    else:&#10;        if not url.endswith('/'):&#10;            url += '/'&#10;        return '%s/%s' % ('/'.join(url.split('/')[0:-2]), database)&#10;&#10;&#10;def _get_pid_column(raw_conn):&#10;    # Some distros (e.g Debian) may inject their branding into server_version&#10;    server_version = raw_conn.execute('SHOW server_version;').first()[0]&#10;    version_string = re.search('^(\d+\.\d+)', server_version).group(0)&#10;    version = [int(x) for x in version_string.split('.')]&#10;    return 'pid' if version >= [9, 2] else 'procpid'&#10;&#10;&#10;def terminate_database_connections(raw_conn, database):&#10;    logger.debug('terminate_database_connections(%r)', database)&#10;    if raw_conn.engine.dialect.name == 'postgresql':&#10;        pid_column = _get_pid_column(raw_conn)&#10;&#10;        raw_conn.execute(&#10;            '''&#10;                SELECT pg_terminate_backend(pg_stat_activity.%(pid_column)s)&#10;                FROM pg_stat_activity&#10;                WHERE&#10;                    pg_stat_activity.datname = '%(database)s' AND&#10;                    %(pid_column)s <> pg_backend_pid();&#10;            ''' % {'pid_column': pid_column, 'database': database}&#10;        )&#10;    else:&#10;        # NotYetImplemented&#10;        pass&#10;&#10;&#10;def create_database(raw_conn, database):&#10;    logger.debug('create_database(%r)', database)&#10;    return sqlalchemy_utils.functions.create_database(&#10;        get_engine_url(raw_conn, database)&#10;    )&#10;&#10;&#10;def copy_database(raw_conn, from_database, to_database):&#10;    logger.debug('copy_database(%r, %r)', from_database, to_database)&#10;    terminate_database_connections(raw_conn, from_database)&#10;&#10;    if raw_conn.engine.dialect.name == 'postgresql':&#10;        raw_conn.execute(&#10;            '''&#10;                CREATE DATABASE &#34;%s&#34; WITH TEMPLATE &#34;%s&#34;;&#10;            ''' %&#10;            (&#10;                to_database,&#10;                from_database&#10;            )&#10;        )&#10;    elif raw_conn.engine.dialect.name == 'mysql':&#10;        # Horribly slow implementation.&#10;        create_database(raw_conn, to_database)&#10;        for row in raw_conn.execute('SHOW TABLES in %s;' % from_database):&#10;            raw_conn.execute('''&#10;                CREATE TABLE %s.%s LIKE %s.%s&#10;            ''' % (&#10;                to_database,&#10;                row[0],&#10;                from_database,&#10;                row[0]&#10;            ))&#10;            raw_conn.execute('ALTER TABLE %s.%s DISABLE KEYS' % (&#10;                to_database,&#10;                row[0]&#10;            ))&#10;            raw_conn.execute('''&#10;                INSERT INTO %s.%s SELECT * FROM %s.%s&#10;            ''' % (&#10;                to_database,&#10;                row[0],&#10;                from_database,&#10;                row[0]&#10;            ))&#10;            raw_conn.execute('ALTER TABLE %s.%s ENABLE KEYS' % (&#10;                to_database,&#10;                row[0]&#10;            ))&#10;    else:&#10;        raise NotSupportedDatabase()&#10;&#10;&#10;def database_exists(raw_conn, database):&#10;    logger.debug('database_exists(%r)', database)&#10;    return sqlalchemy_utils.functions.database_exists(&#10;        get_engine_url(raw_conn, database)&#10;    )&#10;&#10;&#10;def remove_database(raw_conn, database):&#10;    logger.debug('remove_database(%r)', database)&#10;    terminate_database_connections(raw_conn, database)&#10;    return sqlalchemy_utils.functions.drop_database(&#10;        get_engine_url(raw_conn, database)&#10;    )&#10;&#10;&#10;def rename_database(raw_conn, from_database, to_database):&#10;    logger.debug('rename_database(%r, %r)', from_database, to_database)&#10;    terminate_database_connections(raw_conn, from_database)&#10;    if raw_conn.engine.dialect.name == 'postgresql':&#10;        raw_conn.execute(&#10;            '''&#10;                ALTER DATABASE &#34;%s&#34; RENAME TO &#34;%s&#34;&#10;            ''' %&#10;            (&#10;                from_database,&#10;                to_database&#10;            )&#10;        )&#10;    elif raw_conn.engine.dialect.name == 'mysql':&#10;        create_database(raw_conn, to_database)&#10;        for row in raw_conn.execute('SHOW TABLES in %s;' % from_database):&#10;            raw_conn.execute('''&#10;                RENAME TABLE %s.%s TO %s.%s;&#10;            ''' % (&#10;                from_database,&#10;                row[0],&#10;                to_database,&#10;                row[0]&#10;            ))&#10;        remove_database(raw_conn, from_database)&#10;    else:&#10;        raise NotSupportedDatabase()&#10;&#10;&#10;def list_of_databases(raw_conn):&#10;    logger.debug('list_of_databases()')&#10;    if raw_conn.engine.dialect.name == 'postgresql':&#10;        return [&#10;            row[0]&#10;            for row in raw_conn.execute('''&#10;                SELECT datname FROM pg_database&#10;                WHERE datistemplate = false&#10;            ''')&#10;        ]&#10;    elif raw_conn.engine.dialect.name == 'mysql':&#10;        return [&#10;            row[0]&#10;            for row in raw_conn.execute('''SHOW DATABASES''')&#10;        ]&#10;    else:&#10;        raise NotSupportedDatabase()&#10;&#10;"
    signature "None"
  ]
  node [
    id 59
    label "stellar.stellar.operations.NotSupportedDatabase"
    type "class"
    code "class NotSupportedDatabase(Exception): pass"
    signature "NotSupportedDatabase"
  ]
  node [
    id 60
    label "stellar.stellar.operations.get_engine_url"
    type "function"
    code "def get_engine_url(raw_conn, database): url = str(raw_conn.engine.url) if url.count('/') == 3 and url.endswith('/'): return '%s%s' % (url, database) else: if not url.endswith('/'): url += '/' return '%s/%s' % ('/'.join(url.split('/')[0:-2]), database)"
    signature "def get_engine_url(raw_conn, database):"
  ]
  node [
    id 61
    label "stellar.stellar.operations._get_pid_column"
    type "function"
    code "def _get_pid_column(raw_conn): # Some distros (e.g Debian) may inject their branding into server_version server_version = raw_conn.execute('SHOW server_version;').first()[0] version_string = re.search('^(\d+\.\d+)', server_version).group(0) version = [int(x) for x in version_string.split('.')] return 'pid' if version >= [9, 2] else 'procpid'"
    signature "def _get_pid_column(raw_conn): # Some distros (e.g Debian) may inject their branding into server_version:"
  ]
  node [
    id 62
    label "stellar.stellar.operations.terminate_database_connections"
    type "function"
    code "def terminate_database_connections(raw_conn, database): logger.debug('terminate_database_connections(%r)', database) if raw_conn.engine.dialect.name == 'postgresql': pid_column = _get_pid_column(raw_conn)  raw_conn.execute( ''' SELECT pg_terminate_backend(pg_stat_activity.%(pid_column)s) FROM pg_stat_activity WHERE pg_stat_activity.datname = '%(database)s' AND %(pid_column)s <> pg_backend_pid(); ''' % {'pid_column': pid_column, 'database': database} ) else: # NotYetImplemented pass"
    signature "def terminate_database_connections(raw_conn, database):"
  ]
  node [
    id 63
    label "stellar.stellar.operations.create_database"
    type "function"
    code "def create_database(raw_conn, database): logger.debug('create_database(%r)', database) return sqlalchemy_utils.functions.create_database( get_engine_url(raw_conn, database) )"
    signature "def create_database(raw_conn, database):"
  ]
  node [
    id 64
    label "stellar.stellar.operations.copy_database"
    type "function"
    code "def copy_database(raw_conn, from_database, to_database): logger.debug('copy_database(%r, %r)', from_database, to_database) terminate_database_connections(raw_conn, from_database)  if raw_conn.engine.dialect.name == 'postgresql': raw_conn.execute( ''' CREATE DATABASE &#34;%s&#34; WITH TEMPLATE &#34;%s&#34;; ''' % ( to_database, from_database ) ) elif raw_conn.engine.dialect.name == 'mysql': # Horribly slow implementation. create_database(raw_conn, to_database) for row in raw_conn.execute('SHOW TABLES in %s;' % from_database): raw_conn.execute(''' CREATE TABLE %s.%s LIKE %s.%s ''' % ( to_database, row[0], from_database, row[0] )) raw_conn.execute('ALTER TABLE %s.%s DISABLE KEYS' % ( to_database, row[0] )) raw_conn.execute(''' INSERT INTO %s.%s SELECT * FROM %s.%s ''' % ( to_database, row[0], from_database, row[0] )) raw_conn.execute('ALTER TABLE %s.%s ENABLE KEYS' % ( to_database, row[0] )) else: raise NotSupportedDatabase()"
    signature "def copy_database(raw_conn, from_database, to_database):"
  ]
  node [
    id 65
    label "stellar.stellar.operations.database_exists"
    type "function"
    code "def database_exists(raw_conn, database): logger.debug('database_exists(%r)', database) return sqlalchemy_utils.functions.database_exists( get_engine_url(raw_conn, database) )"
    signature "def database_exists(raw_conn, database):"
  ]
  node [
    id 66
    label "stellar.stellar.operations.remove_database"
    type "function"
    code "def remove_database(raw_conn, database): logger.debug('remove_database(%r)', database) terminate_database_connections(raw_conn, database) return sqlalchemy_utils.functions.drop_database( get_engine_url(raw_conn, database) )"
    signature "def remove_database(raw_conn, database):"
  ]
  node [
    id 67
    label "stellar.stellar.operations.rename_database"
    type "function"
    code "def rename_database(raw_conn, from_database, to_database): logger.debug('rename_database(%r, %r)', from_database, to_database) terminate_database_connections(raw_conn, from_database) if raw_conn.engine.dialect.name == 'postgresql': raw_conn.execute( ''' ALTER DATABASE &#34;%s&#34; RENAME TO &#34;%s&#34; ''' % ( from_database, to_database ) ) elif raw_conn.engine.dialect.name == 'mysql': create_database(raw_conn, to_database) for row in raw_conn.execute('SHOW TABLES in %s;' % from_database): raw_conn.execute(''' RENAME TABLE %s.%s TO %s.%s; ''' % ( from_database, row[0], to_database, row[0] )) remove_database(raw_conn, from_database) else: raise NotSupportedDatabase()"
    signature "def rename_database(raw_conn, from_database, to_database):"
  ]
  node [
    id 68
    label "stellar.stellar.operations.list_of_databases"
    type "function"
    code "def list_of_databases(raw_conn): logger.debug('list_of_databases()') if raw_conn.engine.dialect.name == 'postgresql': return [ row[0] for row in raw_conn.execute(''' SELECT datname FROM pg_database WHERE datistemplate = false ''') ] elif raw_conn.engine.dialect.name == 'mysql': return [ row[0] for row in raw_conn.execute('''SHOW DATABASES''') ] else: raise NotSupportedDatabase()"
    signature "def list_of_databases(raw_conn):"
  ]
  node [
    id 69
    label "stellar.stellar.__init__"
    type "module"
    code "from . import app&#10;from . import command&#10;from . import config&#10;from . import models&#10;from . import operations&#10;&#10;__version__ = app.__version__&#10;"
    signature "None"
  ]
  node [
    id 70
    label "stellar.stellar.egg-info"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 71
    label "stellar..pytest_cache"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 72
    label "stellar..pytest_cache.v"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 73
    label "stellar..pytest_cache.v.cache"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 74
    label "stellar.tests"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 75
    label "stellar.tests.test_starts"
    type "module"
    code "import pytest&#10;import stellar&#10;import tempfile&#10;&#10;&#10;class TestCase(object):&#10;    @pytest.yield_fixture(autouse=True)&#10;    def config(self, monkeypatch):&#10;        with tempfile.NamedTemporaryFile() as tmp:&#10;            def load_test_config(self):&#10;                self.config = {&#10;                    'stellar_url': 'sqlite:///%s' % tmp.name,&#10;                    'url': 'sqlite:///%s' % tmp.name,&#10;                    'project_name': 'test_project',&#10;                    'tracked_databases': ['test_database'],&#10;                    'TEST': True&#10;                }&#10;                return None&#10;            monkeypatch.setattr(stellar.app.Stellar, 'load_config', load_test_config)&#10;            yield&#10;&#10;&#10;class Test(TestCase):&#10;    def test_setup_method_works(self, monkeypatch):&#10;        monkeypatch.setattr(&#10;            stellar.app.Stellar,&#10;            'create_stellar_database',&#10;            lambda x: None&#10;        )&#10;        app = stellar.app.Stellar()&#10;        for key in (&#10;            'TEST',&#10;            'stellar_url',&#10;            'url',&#10;            'project_name',&#10;            'tracked_databases',&#10;        ):&#10;            assert app.config[key]&#10;&#10;    def test_shows_not_enough_arguments(self):&#10;        with pytest.raises(SystemExit) as e:&#10;            stellar.command.main()&#10;&#10;    def test_app_context(self, monkeypatch):&#10;        monkeypatch.setattr(&#10;            stellar.app.Stellar,&#10;            'create_stellar_database',&#10;            lambda x: None&#10;        )&#10;        app = stellar.app.Stellar()&#10;"
    signature "None"
  ]
  node [
    id 76
    label "stellar.tests.test_starts.TestCase"
    type "class"
    code "class TestCase(object): @pytest.yield_fixture(autouse=True) def config(self, monkeypatch): with tempfile.NamedTemporaryFile() as tmp: def load_test_config(self): self.config = { 'stellar_url': 'sqlite:///%s' % tmp.name, 'url': 'sqlite:///%s' % tmp.name, 'project_name': 'test_project', 'tracked_databases': ['test_database'], 'TEST': True } return None monkeypatch.setattr(stellar.app.Stellar, 'load_config', load_test_config) yield"
    signature "TestCase"
  ]
  node [
    id 77
    label "stellar.tests.test_starts.TestCase.config"
    type "function"
    code "def config(self, monkeypatch): with tempfile.NamedTemporaryFile() as tmp: def load_test_config(self): self.config = { 'stellar_url': 'sqlite:///%s' % tmp.name, 'url': 'sqlite:///%s' % tmp.name, 'project_name': 'test_project', 'tracked_databases': ['test_database'], 'TEST': True } return None monkeypatch.setattr(stellar.app.Stellar, 'load_config', load_test_config) yield"
    signature "def config(self, monkeypatch):"
  ]
  node [
    id 78
    label "stellar.tests.test_starts.TestCase.config.load_test_config"
    type "function"
    code "def load_test_config(self): self.config = { 'stellar_url': 'sqlite:///%s' % tmp.name, 'url': 'sqlite:///%s' % tmp.name, 'project_name': 'test_project', 'tracked_databases': ['test_database'], 'TEST': True } return None"
    signature "def load_test_config(self):"
  ]
  node [
    id 79
    label "stellar.tests.test_starts.Test"
    type "class"
    code "class Test(TestCase): def test_setup_method_works(self, monkeypatch): monkeypatch.setattr( stellar.app.Stellar, 'create_stellar_database', lambda x: None ) app = stellar.app.Stellar() for key in ( 'TEST', 'stellar_url', 'url', 'project_name', 'tracked_databases', ): assert app.config[key]  def test_shows_not_enough_arguments(self): with pytest.raises(SystemExit) as e: stellar.command.main()  def test_app_context(self, monkeypatch): monkeypatch.setattr( stellar.app.Stellar, 'create_stellar_database', lambda x: None ) app = stellar.app.Stellar()"
    signature "Test"
  ]
  node [
    id 80
    label "stellar.tests.test_starts.Test.test_setup_method_works"
    type "function"
    code "def test_setup_method_works(self, monkeypatch): monkeypatch.setattr( stellar.app.Stellar, 'create_stellar_database', lambda x: None ) app = stellar.app.Stellar() for key in ( 'TEST', 'stellar_url', 'url', 'project_name', 'tracked_databases', ): assert app.config[key]"
    signature "def test_setup_method_works(self, monkeypatch):"
  ]
  node [
    id 81
    label "stellar.tests.test_starts.Test.test_shows_not_enough_arguments"
    type "function"
    code "def test_shows_not_enough_arguments(self): with pytest.raises(SystemExit) as e: stellar.command.main()"
    signature "def test_shows_not_enough_arguments(self):"
  ]
  node [
    id 82
    label "stellar.tests.test_starts.Test.test_app_context"
    type "function"
    code "def test_app_context(self, monkeypatch): monkeypatch.setattr( stellar.app.Stellar, 'create_stellar_database', lambda x: None ) app = stellar.app.Stellar()"
    signature "def test_app_context(self, monkeypatch):"
  ]
  node [
    id 83
    label "stellar.tests.__pycache__"
    type "directory"
    code "None"
    signature "None"
  ]
  node [
    id 84
    label "stellar.tests.test_models"
    type "module"
    code "from stellar.models import get_unique_hash, Table, Snapshot&#10;&#10;&#10;def test_get_unique_hash():&#10;    assert get_unique_hash()&#10;    assert get_unique_hash() != get_unique_hash()&#10;    assert len(get_unique_hash()) == 32&#10;&#10;&#10;def test_table():&#10;    table = Table(&#10;        table_name='hapsu',&#10;        snapshot=Snapshot(&#10;            snapshot_name='snapshot',&#10;            project_name='myproject',&#10;            hash='3330484d0a70eecab84554b5576b4553'&#10;        )&#10;    )&#10;    assert len(table.get_table_name('master')) == 24&#10;"
    signature "None"
  ]
  node [
    id 85
    label "stellar.tests.test_models.test_get_unique_hash"
    type "function"
    code "def test_get_unique_hash(): assert get_unique_hash() assert get_unique_hash() != get_unique_hash() assert len(get_unique_hash()) == 32"
    signature "def test_get_unique_hash():"
  ]
  node [
    id 86
    label "stellar.tests.test_models.test_table"
    type "function"
    code "def test_table(): table = Table( table_name='hapsu', snapshot=Snapshot( snapshot_name='snapshot', project_name='myproject', hash='3330484d0a70eecab84554b5576b4553' ) ) assert len(table.get_table_name('master')) == 24"
    signature "def test_table():"
  ]
  node [
    id 87
    label "stellar.tests.test_operations"
    type "module"
    code "import pytest&#10;&#10;from stellar.operations import _get_pid_column&#10;&#10;&#10;class ConnectionMock(object):&#10;    def __init__(self, version):&#10;        self.version = version&#10;&#10;    def execute(self, query):&#10;        return self&#10;&#10;    def first(self):&#10;        return [self.version]&#10;&#10;&#10;class TestGetPidColumn(object):&#10;    @pytest.mark.parametrize('version', ['9.1', '8.9', '9.1.9', '8.9.9'])&#10;    def test_returns_procpid_for_version_older_than_9_2(self, version):&#10;        raw_conn = ConnectionMock(version=version)&#10;        assert _get_pid_column(raw_conn) == 'procpid'&#10;&#10;    @pytest.mark.parametrize('version', [&#10;        '9.2', '9.3', '10.0', '9.2.1', '9.6beta1', '10.1.1',&#10;        '10.3 (Ubuntu 10.3-1.pgdg16.04+1)'&#10;    ])&#10;    def test_returns_pid_for_version_equal_or_newer_than_9_2(self, version):&#10;        raw_conn = ConnectionMock(version=version)&#10;        assert _get_pid_column(raw_conn) == 'pid'&#10;"
    signature "None"
  ]
  node [
    id 88
    label "stellar.tests.test_operations.ConnectionMock"
    type "class"
    code "class ConnectionMock(object): def __init__(self, version): self.version = version  def execute(self, query): return self  def first(self): return [self.version]"
    signature "ConnectionMock"
  ]
  node [
    id 89
    label "stellar.tests.test_operations.ConnectionMock.__init__"
    type "function"
    code "def __init__(self, version): self.version = version"
    signature "def __init__(self, version):"
  ]
  node [
    id 90
    label "stellar.tests.test_operations.ConnectionMock.execute"
    type "function"
    code "def execute(self, query): return self"
    signature "def execute(self, query):"
  ]
  node [
    id 91
    label "stellar.tests.test_operations.ConnectionMock.first"
    type "function"
    code "def first(self): return [self.version]"
    signature "def first(self):"
  ]
  node [
    id 92
    label "stellar.tests.test_operations.TestGetPidColumn"
    type "class"
    code "class TestGetPidColumn(object): @pytest.mark.parametrize('version', ['9.1', '8.9', '9.1.9', '8.9.9']) def test_returns_procpid_for_version_older_than_9_2(self, version): raw_conn = ConnectionMock(version=version) assert _get_pid_column(raw_conn) == 'procpid'  @pytest.mark.parametrize('version', [ '9.2', '9.3', '10.0', '9.2.1', '9.6beta1', '10.1.1', '10.3 (Ubuntu 10.3-1.pgdg16.04+1)' ]) def test_returns_pid_for_version_equal_or_newer_than_9_2(self, version): raw_conn = ConnectionMock(version=version) assert _get_pid_column(raw_conn) == 'pid'"
    signature "TestGetPidColumn"
  ]
  node [
    id 93
    label "stellar.tests.test_operations.TestGetPidColumn.test_returns_procpid_for_version_older_than_9_2"
    type "function"
    code "def test_returns_procpid_for_version_older_than_9_2(self, version): raw_conn = ConnectionMock(version=version) assert _get_pid_column(raw_conn) == 'procpid'"
    signature "def test_returns_procpid_for_version_older_than_9_2(self, version):"
  ]
  node [
    id 94
    label "stellar.tests.test_operations.TestGetPidColumn.test_returns_pid_for_version_equal_or_newer_than_9_2"
    type "function"
    code "def test_returns_pid_for_version_equal_or_newer_than_9_2(self, version): raw_conn = ConnectionMock(version=version) assert _get_pid_column(raw_conn) == 'pid'"
    signature "def test_returns_pid_for_version_equal_or_newer_than_9_2(self, version):"
  ]
  node [
    id 95
    label "stellar.setup"
    type "module"
    code "# coding: utf-8&#10;import os&#10;import re&#10;&#10;from setuptools import setup, find_packages&#10;&#10;&#10;# https://bitbucket.org/zzzeek/alembic/raw/f38eaad4a80d7e3d893c3044162971971ae0&#10;# 09bf/setup.py&#10;with open(&#10;    os.path.join(os.path.dirname(__file__), 'stellar', 'app.py')&#10;) as app_file:&#10;    VERSION = re.compile(&#10;        r&#34;.*__version__ = '(.*?)'&#34;, re.S&#10;    ).match(app_file.read()).group(1)&#10;&#10;with open(&#34;README.md&#34;) as readme:&#10;    long_description = readme.read()&#10;&#10;setup(&#10;    name='stellar',&#10;    description=(&#10;        'stellar is a tool for creating and restoring database snapshots'&#10;    ),&#10;    long_description=long_description,&#10;    version=VERSION,&#10;    url='https://github.com/fastmonkeys/stellar',&#10;    license='BSD',&#10;    author=u'Teemu Kokkonen, Pekka P&#246;yry',&#10;    author_email='teemu@fastmonkeys.com, pekka@fastmonkeys.com',&#10;    packages=find_packages('.', exclude=['examples*', 'test*']),&#10;    entry_points={&#10;        'console_scripts': [ 'stellar = stellar.command:main' ],&#10;    },&#10;    zip_safe=False,&#10;    include_package_data=True,&#10;    platforms='any',&#10;    classifiers=[&#10;        'Intended Audience :: Developers',&#10;        'License :: OSI Approved :: BSD License',&#10;        'Operating System :: POSIX',&#10;        'Operating System :: Microsoft :: Windows',&#10;        'Operating System :: MacOS :: MacOS X',&#10;        'Topic :: Utilities',&#10;        'Programming Language :: Python :: 2',&#10;        'Programming Language :: Python :: 3',&#10;        'Topic :: Database',&#10;        'Topic :: Software Development :: Version Control',&#10;    ],&#10;    install_requires = [&#10;        'PyYAML>=3.11',&#10;        'SQLAlchemy>=0.9.6',&#10;        'humanize>=0.5.1',&#10;        'schema>=0.3.1',&#10;        'click>=3.1',&#10;        'SQLAlchemy-Utils>=0.26.11',&#10;        'psutil>=2.1.1',&#10;    ]&#10;)&#10;"
    signature "None"
  ]
  node [
    id 96
    label "os"
    type "local_module"
    code "None"
    signature "None"
  ]
  node [
    id 97
    label "re"
    type "local_module"
    code "None"
    signature "None"
  ]
  node [
    id 98
    label "logging"
    type "local_module"
    code "None"
    signature "None"
  ]
  node [
    id 99
    label "sys"
    type "standard_library"
    code "None"
    signature "None"
  ]
  node [
    id 100
    label "click"
    type "unknown"
    code "None"
    signature "None"
  ]
  node [
    id 101
    label "yaml"
    type "third_party_library"
    code "None"
    signature "None"
  ]
  node [
    id 102
    label "hashlib"
    type "local_module"
    code "None"
    signature "None"
  ]
  node [
    id 103
    label "uuid"
    type "local_module"
    code "None"
    signature "None"
  ]
  node [
    id 104
    label "humanize"
    type "unknown"
    code "None"
    signature "None"
  ]
  node [
    id 105
    label "sqlalchemy_utils"
    type "unknown"
    code "None"
    signature "None"
  ]
  node [
    id 106
    label "pytest"
    type "unknown"
    code "None"
    signature "None"
  ]
  node [
    id 107
    label "tempfile"
    type "local_module"
    code "None"
    signature "None"
  ]
  edge [
    source 0
    target 1
    relationship "CONTAINS"
  ]
  edge [
    source 0
    target 70
    relationship "CONTAINS"
  ]
  edge [
    source 0
    target 71
    relationship "CONTAINS"
  ]
  edge [
    source 0
    target 74
    relationship "CONTAINS"
  ]
  edge [
    source 0
    target 95
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 2
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 25
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 31
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 39
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 40
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 57
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 58
    relationship "CONTAINS"
  ]
  edge [
    source 1
    target 69
    relationship "CONTAINS"
  ]
  edge [
    source 2
    target 3
    relationship "CONTAINS"
  ]
  edge [
    source 2
    target 5
    relationship "CONTAINS"
  ]
  edge [
    source 2
    target 98
    relationship "IMPORTS"
  ]
  edge [
    source 2
    target 96
    relationship "IMPORTS"
  ]
  edge [
    source 2
    target 99
    relationship "IMPORTS"
  ]
  edge [
    source 2
    target 100
    relationship "IMPORTS"
  ]
  edge [
    source 3
    target 4
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 6
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 7
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 8
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 9
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 10
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 11
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 12
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 13
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 14
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 15
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 16
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 17
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 18
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 19
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 20
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 21
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 22
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 23
    relationship "CONTAINS"
  ]
  edge [
    source 5
    target 24
    relationship "CONTAINS"
  ]
  edge [
    source 6
    target 7
    relationship "CALLS"
  ]
  edge [
    source 6
    target 8
    relationship "CALLS"
  ]
  edge [
    source 7
    target 29
    relationship "CALLS"
  ]
  edge [
    source 8
    target 3
    relationship "CALLS"
  ]
  edge [
    source 8
    target 9
    relationship "CALLS"
  ]
  edge [
    source 8
    target 10
    relationship "CALLS"
  ]
  edge [
    source 9
    target 65
    relationship "CALLS"
  ]
  edge [
    source 9
    target 63
    relationship "CALLS"
  ]
  edge [
    source 11
    target 91
    relationship "CALLS"
  ]
  edge [
    source 13
    target 91
    relationship "CALLS"
  ]
  edge [
    source 14
    target 33
    relationship "CALLS"
  ]
  edge [
    source 14
    target 49
    relationship "CALLS"
  ]
  edge [
    source 14
    target 36
    relationship "CALLS"
  ]
  edge [
    source 14
    target 37
    relationship "CALLS"
  ]
  edge [
    source 14
    target 64
    relationship "CALLS"
  ]
  edge [
    source 14
    target 18
    relationship "CALLS"
  ]
  edge [
    source 15
    target 66
    relationship "CALLS"
  ]
  edge [
    source 15
    target 37
    relationship "CALLS"
  ]
  edge [
    source 17
    target 65
    relationship "CALLS"
  ]
  edge [
    source 17
    target 37
    relationship "CALLS"
  ]
  edge [
    source 17
    target 66
    relationship "CALLS"
  ]
  edge [
    source 17
    target 67
    relationship "CALLS"
  ]
  edge [
    source 17
    target 18
    relationship "CALLS"
  ]
  edge [
    source 18
    target 8
    relationship "CALLS"
  ]
  edge [
    source 18
    target 3
    relationship "CALLS"
  ]
  edge [
    source 18
    target 19
    relationship "CALLS"
  ]
  edge [
    source 19
    target 64
    relationship "CALLS"
  ]
  edge [
    source 19
    target 37
    relationship "CALLS"
  ]
  edge [
    source 21
    target 37
    relationship "CALLS"
  ]
  edge [
    source 21
    target 65
    relationship "CALLS"
  ]
  edge [
    source 22
    target 37
    relationship "CALLS"
  ]
  edge [
    source 22
    target 65
    relationship "CALLS"
  ]
  edge [
    source 22
    target 67
    relationship "CALLS"
  ]
  edge [
    source 22
    target 42
    relationship "CALLS"
  ]
  edge [
    source 23
    target 37
    relationship "CALLS"
  ]
  edge [
    source 23
    target 68
    relationship "CALLS"
  ]
  edge [
    source 23
    target 66
    relationship "CALLS"
  ]
  edge [
    source 23
    target 47
    relationship "CALLS"
  ]
  edge [
    source 25
    target 26
    relationship "CONTAINS"
  ]
  edge [
    source 25
    target 27
    relationship "CONTAINS"
  ]
  edge [
    source 25
    target 28
    relationship "CONTAINS"
  ]
  edge [
    source 25
    target 29
    relationship "CONTAINS"
  ]
  edge [
    source 25
    target 30
    relationship "CONTAINS"
  ]
  edge [
    source 25
    target 96
    relationship "IMPORTS"
  ]
  edge [
    source 25
    target 98
    relationship "IMPORTS"
  ]
  edge [
    source 25
    target 101
    relationship "IMPORTS"
  ]
  edge [
    source 29
    target 27
    relationship "CALLS"
  ]
  edge [
    source 29
    target 26
    relationship "CALLS"
  ]
  edge [
    source 30
    target 28
    relationship "CALLS"
  ]
  edge [
    source 31
    target 32
    relationship "CONTAINS"
  ]
  edge [
    source 31
    target 33
    relationship "CONTAINS"
  ]
  edge [
    source 31
    target 36
    relationship "CONTAINS"
  ]
  edge [
    source 31
    target 102
    relationship "IMPORTS"
  ]
  edge [
    source 31
    target 103
    relationship "IMPORTS"
  ]
  edge [
    source 33
    target 34
    relationship "CONTAINS"
  ]
  edge [
    source 33
    target 35
    relationship "CONTAINS"
  ]
  edge [
    source 36
    target 37
    relationship "CONTAINS"
  ]
  edge [
    source 36
    target 38
    relationship "CONTAINS"
  ]
  edge [
    source 39
    target 56
    relationship "CALLS"
  ]
  edge [
    source 40
    target 41
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 43
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 44
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 45
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 46
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 48
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 50
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 51
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 52
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 53
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 54
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 55
    relationship "CONTAINS"
  ]
  edge [
    source 40
    target 56
    relationship "CALLS"
  ]
  edge [
    source 40
    target 99
    relationship "IMPORTS"
  ]
  edge [
    source 40
    target 104
    relationship "IMPORTS"
  ]
  edge [
    source 40
    target 100
    relationship "IMPORTS"
  ]
  edge [
    source 40
    target 98
    relationship "IMPORTS"
  ]
  edge [
    source 41
    target 42
    relationship "CONTAINS"
  ]
  edge [
    source 41
    target 21
    relationship "CALLS"
  ]
  edge [
    source 41
    target 22
    relationship "CALLS"
  ]
  edge [
    source 41
    target 30
    relationship "CALLS"
  ]
  edge [
    source 43
    target 5
    relationship "CALLS"
  ]
  edge [
    source 43
    target 41
    relationship "CALLS"
  ]
  edge [
    source 46
    target 47
    relationship "CONTAINS"
  ]
  edge [
    source 46
    target 43
    relationship "CALLS"
  ]
  edge [
    source 46
    target 41
    relationship "CALLS"
  ]
  edge [
    source 46
    target 23
    relationship "CALLS"
  ]
  edge [
    source 48
    target 49
    relationship "CONTAINS"
  ]
  edge [
    source 48
    target 43
    relationship "CALLS"
  ]
  edge [
    source 48
    target 41
    relationship "CALLS"
  ]
  edge [
    source 48
    target 11
    relationship "CALLS"
  ]
  edge [
    source 48
    target 14
    relationship "CALLS"
  ]
  edge [
    source 50
    target 12
    relationship "CALLS"
  ]
  edge [
    source 50
    target 43
    relationship "CALLS"
  ]
  edge [
    source 51
    target 43
    relationship "CALLS"
  ]
  edge [
    source 51
    target 13
    relationship "CALLS"
  ]
  edge [
    source 51
    target 29
    relationship "CALLS"
  ]
  edge [
    source 51
    target 11
    relationship "CALLS"
  ]
  edge [
    source 51
    target 20
    relationship "CALLS"
  ]
  edge [
    source 51
    target 19
    relationship "CALLS"
  ]
  edge [
    source 51
    target 17
    relationship "CALLS"
  ]
  edge [
    source 52
    target 43
    relationship "CALLS"
  ]
  edge [
    source 52
    target 11
    relationship "CALLS"
  ]
  edge [
    source 52
    target 15
    relationship "CALLS"
  ]
  edge [
    source 53
    target 43
    relationship "CALLS"
  ]
  edge [
    source 53
    target 11
    relationship "CALLS"
  ]
  edge [
    source 53
    target 16
    relationship "CALLS"
  ]
  edge [
    source 54
    target 43
    relationship "CALLS"
  ]
  edge [
    source 54
    target 11
    relationship "CALLS"
  ]
  edge [
    source 54
    target 15
    relationship "CALLS"
  ]
  edge [
    source 54
    target 14
    relationship "CALLS"
  ]
  edge [
    source 55
    target 68
    relationship "CALLS"
  ]
  edge [
    source 55
    target 65
    relationship "CALLS"
  ]
  edge [
    source 56
    target 44
    relationship "CALLS"
  ]
  edge [
    source 58
    target 59
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 60
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 61
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 62
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 63
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 64
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 65
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 66
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 67
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 68
    relationship "CONTAINS"
  ]
  edge [
    source 58
    target 98
    relationship "IMPORTS"
  ]
  edge [
    source 58
    target 97
    relationship "IMPORTS"
  ]
  edge [
    source 58
    target 105
    relationship "IMPORTS"
  ]
  edge [
    source 61
    target 91
    relationship "CALLS"
  ]
  edge [
    source 61
    target 90
    relationship "CALLS"
  ]
  edge [
    source 62
    target 61
    relationship "CALLS"
  ]
  edge [
    source 62
    target 90
    relationship "CALLS"
  ]
  edge [
    source 63
    target 63
    relationship "CALLS"
  ]
  edge [
    source 63
    target 60
    relationship "CALLS"
  ]
  edge [
    source 64
    target 62
    relationship "CALLS"
  ]
  edge [
    source 64
    target 90
    relationship "CALLS"
  ]
  edge [
    source 64
    target 63
    relationship "CALLS"
  ]
  edge [
    source 64
    target 59
    relationship "CALLS"
  ]
  edge [
    source 65
    target 65
    relationship "CALLS"
  ]
  edge [
    source 65
    target 60
    relationship "CALLS"
  ]
  edge [
    source 66
    target 62
    relationship "CALLS"
  ]
  edge [
    source 66
    target 60
    relationship "CALLS"
  ]
  edge [
    source 67
    target 62
    relationship "CALLS"
  ]
  edge [
    source 67
    target 90
    relationship "CALLS"
  ]
  edge [
    source 67
    target 63
    relationship "CALLS"
  ]
  edge [
    source 67
    target 66
    relationship "CALLS"
  ]
  edge [
    source 67
    target 59
    relationship "CALLS"
  ]
  edge [
    source 68
    target 90
    relationship "CALLS"
  ]
  edge [
    source 68
    target 59
    relationship "CALLS"
  ]
  edge [
    source 71
    target 72
    relationship "CONTAINS"
  ]
  edge [
    source 72
    target 73
    relationship "CONTAINS"
  ]
  edge [
    source 74
    target 75
    relationship "CONTAINS"
  ]
  edge [
    source 74
    target 83
    relationship "CONTAINS"
  ]
  edge [
    source 74
    target 84
    relationship "CONTAINS"
  ]
  edge [
    source 74
    target 87
    relationship "CONTAINS"
  ]
  edge [
    source 75
    target 76
    relationship "CONTAINS"
  ]
  edge [
    source 75
    target 79
    relationship "CONTAINS"
  ]
  edge [
    source 75
    target 106
    relationship "IMPORTS"
  ]
  edge [
    source 75
    target 0
    relationship "IMPORTS"
  ]
  edge [
    source 75
    target 107
    relationship "IMPORTS"
  ]
  edge [
    source 76
    target 77
    relationship "CONTAINS"
  ]
  edge [
    source 77
    target 78
    relationship "CONTAINS"
  ]
  edge [
    source 79
    target 80
    relationship "CONTAINS"
  ]
  edge [
    source 79
    target 81
    relationship "CONTAINS"
  ]
  edge [
    source 79
    target 82
    relationship "CONTAINS"
  ]
  edge [
    source 80
    target 5
    relationship "CALLS"
  ]
  edge [
    source 81
    target 56
    relationship "CALLS"
  ]
  edge [
    source 82
    target 5
    relationship "CALLS"
  ]
  edge [
    source 84
    target 85
    relationship "CONTAINS"
  ]
  edge [
    source 84
    target 86
    relationship "CONTAINS"
  ]
  edge [
    source 85
    target 32
    relationship "CALLS"
  ]
  edge [
    source 86
    target 36
    relationship "CALLS"
  ]
  edge [
    source 86
    target 33
    relationship "CALLS"
  ]
  edge [
    source 86
    target 37
    relationship "CALLS"
  ]
  edge [
    source 87
    target 88
    relationship "CONTAINS"
  ]
  edge [
    source 87
    target 92
    relationship "CONTAINS"
  ]
  edge [
    source 87
    target 106
    relationship "IMPORTS"
  ]
  edge [
    source 88
    target 89
    relationship "CONTAINS"
  ]
  edge [
    source 88
    target 90
    relationship "CONTAINS"
  ]
  edge [
    source 88
    target 91
    relationship "CONTAINS"
  ]
  edge [
    source 92
    target 93
    relationship "CONTAINS"
  ]
  edge [
    source 92
    target 94
    relationship "CONTAINS"
  ]
  edge [
    source 93
    target 88
    relationship "CALLS"
  ]
  edge [
    source 93
    target 61
    relationship "CALLS"
  ]
  edge [
    source 94
    target 88
    relationship "CALLS"
  ]
  edge [
    source 94
    target 61
    relationship "CALLS"
  ]
  edge [
    source 95
    target 96
    relationship "IMPORTS"
  ]
  edge [
    source 95
    target 97
    relationship "IMPORTS"
  ]
]
