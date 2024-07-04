from sqlalchemy import MetaData, Table, Column, Integer, String, Sequence

metadata = MetaData()


vacancies = Table(
    "vacancies",
    metadata,
    Column("id", Integer, Sequence("vac_id_seq"), primary_key=True,),
    Column("title", String),
    Column("area", String),
    Column("company_name", String),
    Column("experience", String),
    Column("salary", Integer),
    Column("currency",  String),
    Column("url", String)
)
