"""
Universal Generic Data Generator Engine for TDM.
Automatically inspects the loaded SQLAlchemy models and generates relational,
semantically correct, and scale-adjusted synthetic test data dynamically.
"""

import datetime
import random
from decimal import Decimal
from faker import Faker
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.db import Base
from app.logger import get_logger

logger = get_logger(__name__)
fake = Faker()

def generate_universal_data(db: Session, scale_factor: float = 1.0) -> None:
    """
    Universally and dynamically generates synthetic test data for any domain models
    currently registered on the Base.metadata.
    Uses topological sorting of tables to guarantee perfect foreign key referential integrity.
    """
    # Get sorted list of tables by dependency order (topological sort)
    sorted_tables = Base.metadata.sorted_tables
    if not sorted_tables:
        logger.info("No active models/tables loaded in metadata to generate data for.")
        return

    logger.info(f"Starting universal data generation for tables: {[t.name for t in sorted_tables]} with scale={scale_factor}")
    
    # Track generated primary keys: table_name -> list of primary keys
    generated_ids = {}

    for table in sorted_tables:
        table_name = table.name
        
        # Resolve SQLAlchemy model class from the loaded mapper registry
        model_class = None
        for mapper in Base.registry.mappers:
            if mapper.local_table.name == table_name:
                model_class = mapper.class_
                break

        if not model_class:
            logger.warning(f"Could not find SQLAlchemy mapped class for table: {table_name}")
            continue

        # Determine target number of rows to generate
        # Base tables (no foreign keys) get a baseline of 500 rows.
        # Relational/transactional tables (have foreign keys) get 1000 rows.
        has_fks = any(col.foreign_keys for col in table.columns)
        base_rows = 1000 if has_fks else 500
        target_count = int(base_rows * scale_factor)
        
        # Ensure we always generate at least a minimum set (e.g. min 10) so relationships can match properly
        target_count = max(10, target_count)

        logger.info(f"Generating {target_count} rows for table: {table_name}")

        for _ in range(target_count):
            row_attrs = {}
            for col in table.columns:
                # A. Skip auto-incrementing primary keys
                if col.primary_key and col.default is None and not col.foreign_keys:
                    continue

                # B. Handle Foreign Keys (Link to parent records)
                if col.foreign_keys:
                    fk = list(col.foreign_keys)[0]
                    parent_table_name = fk.column.table.name
                    parent_pks = generated_ids.get(parent_table_name, [])
                    row_attrs[col.name] = random.choice(parent_pks) if parent_pks else None
                    continue

                # C. Generate Random Data based on column name & Python type
                col_name_lower = col.name.lower()
                
                try:
                    python_type = col.type.python_type
                except NotImplementedError:
                    # Fallback if python_type is not implemented for a custom dialect type
                    python_type = str

                if python_type == str:
                    if col.unique:
                        if "email" in col_name_lower:
                            row_attrs[col.name] = fake.unique.email()
                        elif "phone" in col_name_lower:
                            row_attrs[col.name] = fake.unique.phone_number()
                        elif "name" in col_name_lower:
                            row_attrs[col.name] = fake.unique.word()
                        elif "code" in col_name_lower or "number" in col_name_lower or "sku" in col_name_lower or "id_string" in col_name_lower:
                            row_attrs[col.name] = fake.unique.bothify(text="BILL-#####") if "bill" in table_name else fake.unique.bothify(text="CODE-#####")
                        else:
                            row_attrs[col.name] = fake.unique.word()
                    elif "first_name" in col_name_lower:
                        row_attrs[col.name] = fake.first_name()
                    elif "last_name" in col_name_lower:
                        row_attrs[col.name] = fake.last_name()
                    elif "email" in col_name_lower:
                        row_attrs[col.name] = fake.email()
                    elif "phone" in col_name_lower:
                        row_attrs[col.name] = fake.phone_number()
                    elif "gender" in col_name_lower:
                        row_attrs[col.name] = random.choice(["Male", "Female", "Other"]) if random.random() < 0.85 else None
                    elif "code" in col_name_lower or "number" in col_name_lower or "sku" in col_name_lower or "id_string" in col_name_lower:
                        row_attrs[col.name] = fake.unique.bothify(text="BILL-#####") if "bill" in table_name else fake.unique.bothify(text="CODE-#####")
                    elif "address" in col_name_lower:
                        row_attrs[col.name] = fake.street_address()
                    elif "city" in col_name_lower:
                        row_attrs[col.name] = fake.city()
                    elif "state" in col_name_lower:
                        row_attrs[col.name] = fake.state_abbr()
                    elif "country" in col_name_lower:
                        row_attrs[col.name] = fake.country()
                    elif "zip" in col_name_lower or "postal" in col_name_lower:
                        row_attrs[col.name] = fake.zipcode()
                    elif "description" in col_name_lower:
                        row_attrs[col.name] = fake.paragraph(nb_sentences=2)
                    elif "status" in col_name_lower:
                        row_attrs[col.name] = random.choice(["Pending", "Active", "Completed", "Cancelled"])
                    else:
                        row_attrs[col.name] = fake.word()
                elif python_type == int:
                    if "age" in col_name_lower:
                        row_attrs[col.name] = random.randint(18, 90)
                    elif "quantity" in col_name_lower or "qty" in col_name_lower:
                        row_attrs[col.name] = random.randint(1, 10)
                    elif "year" in col_name_lower:
                        row_attrs[col.name] = random.randint(2010, 2026)
                    else:
                        row_attrs[col.name] = random.randint(100, 9999)
                elif python_type in (float, Decimal):
                    if "price" in col_name_lower or "amount" in col_name_lower or "rate" in col_name_lower or "cost" in col_name_lower or "balance" in col_name_lower:
                        row_attrs[col.name] = round(random.uniform(10.0, 15000.0), 2)
                    else:
                        row_attrs[col.name] = round(random.uniform(0.0, 100.0), 2)
                elif python_type == bool:
                    if "cancel" in col_name_lower:
                        row_attrs[col.name] = random.choice([True, False]) if random.random() < 0.15 else False
                    else:
                        row_attrs[col.name] = random.choice([True, False])
                elif python_type == datetime.date:
                    if "dob" in col_name_lower or "birth" in col_name_lower:
                        row_attrs[col.name] = fake.date_of_birth(minimum_age=0, maximum_age=100)
                    elif "date" in col_name_lower:
                        row_attrs[col.name] = fake.date_between(start_date="-2y", end_date="today")
                    else:
                        row_attrs[col.name] = datetime.date.today()
                elif python_type == datetime.datetime:
                    if "date" in col_name_lower or "time" in col_name_lower or "created" in col_name_lower:
                        row_attrs[col.name] = fake.date_time_between(start_date="-2y", end_date="now")
                    else:
                        row_attrs[col.name] = datetime.datetime.now()
                else:
                    row_attrs[col.name] = None

            # Create SQLAlchemy model instance
            instance = model_class(**row_attrs)
            db.add(instance)
            db.flush() # Flush to load database-generated auto-incremented primary keys

            # Track primary key values of generated row
            pk_col = table.primary_key.columns.values()[0].name
            if table_name not in generated_ids:
                generated_ids[table_name] = []
            generated_ids[table_name].append(getattr(instance, pk_col))

        db.commit()
    logger.info("Universal dynamic data generation completed successfully!")
