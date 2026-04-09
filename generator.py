import random
from faker import Faker
from sqlalchemy.orm import Session
from models import Office, Employee, ProductLine, Product, Customer, Order, OrderDetail, Payment

fake = Faker()

def generate_base_data(db: Session, scale_factor=1.0):
    # Scale factor allows us to run a subset of the data for local POC testing. 
    # scale_factor = 1.0 means full requirement size: 5 offices, 500 employees, 50 product-lines, 25k products, 10k customers
    num_offices = max(1, int(5 * scale_factor))
    emps_per_office = max(10, int(100 * scale_factor))
    num_pl = max(1, int(50 * scale_factor))
    prods_per_pl = max(1, int(500 * scale_factor))
    num_customers = max(1, int(10000 * scale_factor))

    # 1. Generate Offices
    # Generating +1 extra office to explicitly satisfy "offices without employees"
    offices = []
    for i in range(num_offices + 1):
        office = Office(
            officeCode=str(i+1),
            city=fake.city(),
            phone=fake.phone_number()[:50],
            addressLine1=fake.street_address()[:50],
            country=fake.country()[:50],
            postalCode=fake.postcode()[:15],
            territory=fake.word()[:10]
        )
        offices.append(office)
    db.add_all(offices)
    db.commit()

    # 2. Generate Employees
    # For valid/invalid constraint: employee with manager vs without manager
    # Let's say 90% have manager, 10% no manager. Or per requirements "define percentage".
    employees = []
    emp_ids = list(range(1, (num_offices * emps_per_office) + 1))
    
    for i, emp_id in enumerate(emp_ids):
        # 10% employees without manager (reportsTo = None), rest get random manager from previously created
        reports_to = None
        if i > 0 and random.random() < 0.90:
            reports_to = random.choice(emp_ids[:i])
            
        emp = Employee(
            employeeNumber=emp_id,
            lastName=fake.last_name(),
            firstName=fake.first_name(),
            extension=fake.bothify(text='x####'),
            email=fake.email(),
            officeCode=str((i % num_offices) + 1),
            reportsTo=reports_to,
            jobTitle=fake.job()[:50]
        )
        employees.append(emp)
    db.add_all(employees)
    db.commit()

    # 3. Product lines & Products
    print("Generating products...")
    for i in range(num_pl):
        pl_name = fake.word() + str(i)
        pl = ProductLine(
            productLine=pl_name[:50],
            textDescription=fake.text()
        )
        db.add(pl)
        db.commit()
        
        products = []
        for j in range(prods_per_pl):
            prod = Product(
                productCode=f"P{i}-{j}",
                productName=fake.catch_phrase()[:70],
                productLine=pl.productLine,
                productScale="1:10",
                productVendor=fake.company()[:50],
                productDescription=fake.text(),
                quantityInStock=random.randint(10, 1000),
                buyPrice=round(random.uniform(10.0, 100.0), 2),
                MSRP=round(random.uniform(110.0, 200.0), 2)
            )
            products.append(prod)
        db.add_all(products)
        db.commit()

    # 4. Customers
    print("Generating Customers...")
    customers = []
    for i in range(1, num_customers + 1):
        cust = Customer(
            customerNumber=i,
            customerName=fake.company()[:50],
            contactLastName=fake.last_name(),
            contactFirstName=fake.first_name(),
            phone=fake.phone_number()[:50],
            addressLine1=fake.street_address()[:50],
            city=fake.city()[:50],
            country=fake.country()[:50],
            salesRepEmployeeNumber=random.choice(emp_ids)
        )
        customers.append(cust)
    db.add_all(customers)
    db.commit()


def generate_transactional_data(db: Session, scale_factor=1.0):
    num_customers = max(1, int(10000 * scale_factor))
    prods_per_pl = max(1, int(500 * scale_factor))
    num_pl = max(1, int(50 * scale_factor))
    total_products = num_pl * prods_per_pl

    # 10 orders per customer
    order_id = 1
    
    # Validation Rules
    # order with payments: 70%
    # order without payment: 20%
    # order with multiple payments: 10%
    
    for cust_id in range(1, num_customers + 1):
        for _ in range(10):
            # Generate Order
            order = Order(
                orderNumber=order_id,
                orderDate=fake.date_this_year(),
                requiredDate=fake.date_this_year(),
                status=random.choice(["Shipped", "In Process", "Cancelled"]),
                customerNumber=cust_id
            )
            db.add(order)
            
            # Generate Order Detail
            # Just grabbing random product code
            p_idx_pl = random.randint(0, num_pl - 1)
            p_idx_pr = random.randint(0, prods_per_pl - 1)
            p_code = f"P{p_idx_pl}-{p_idx_pr}"
            
            od = OrderDetail(
                orderNumber=order_id,
                productCode=p_code,
                quantityOrdered=random.randint(1, 50),
                priceEach=round(random.uniform(10.0, 100.0), 2),
                orderLineNumber=1
            )
            db.add(od)
            
            # Generate payments based on valid/invalid constraints
            rand_val = random.random()
            num_payments = 0
            if rand_val < 0.7:
                num_payments = 1
            elif rand_val < 0.8:
                num_payments = 2 # Multiple payments
                
            for k in range(num_payments):
                payment = Payment(
                    customerNumber=cust_id,
                    checkNumber=fake.bothify(text='??#######') + f"{order_id}{k}",
                    paymentDate=fake.date_this_year(),
                    amount=round(random.uniform(50.0, 500.0), 2)
                )
                db.add(payment)
                
            order_id += 1
            
        # Commit per customer to avoid huge memory spike for POC
        db.commit()
