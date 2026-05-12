import sqlite3

DB_NAME = "controlgroup.db"


def print_divider() -> None:
    print("\n" + "-" * 40)


def pause() -> None:
    input("\nPress Enter to continue:")


def print_menu() -> None:
    print_divider()
    print("Control Group Consortium Menu")
    print("*** View ***")
    print("1.  View all institutions")
    print("2.  View all researchers")
    print("3.  View all experiments")
    print("4.  View all funding sources")
    print("5.  View all charges")
    print("6.  View all charge adjustments")
    print("*** Manage Researchers & Experiments ***")
    print("7.  Add a researcher")
    print("8.  Add an experiment")
    print("9.  Assign researcher to experiment")
    print("10. Remove a researcher")
    print("11. Remove an experiment")
    print("12. Unassign researcher from experiment")
    print("*** Manage Charges ***")
    print("13. Add a charge")
    print("14. Add a charge adjustment")
    print("15. Remove a charge")
    print("16. Remove a charge adjustment")
    print("17. Quit")


def welcome_screen() -> None:
    print_divider()
    print("Welcome to the Control Group Consortium Database!")
    print("Use the menu to browse/manage experiments, charges, researchers, etc.")
    pause()

# institutionId, institutionName, institutionType (sort by ASC alphabetical order of name)
# experimentId, experimentName, startDate, endDate (sort by DESC startDate)
def view_institutions(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        "SELECT institutionId, institutionName, institutionType FROM institution ORDER BY institutionName"
    )
    institutions = cursor.fetchall()

    print_divider()
    print("Institutions")

    if institutions:
        for inst_id, inst_name, inst_type in institutions:
            print(f"\n  [{inst_id}] {inst_name} ({inst_type})")
            cursor.execute(
                """
                SELECT DISTINCT e.experimentId, e.name, e.startDate, e.endDate
                FROM experiment e
                JOIN researcher_experiment re ON e.experimentId = re.experimentId
                JOIN researcher r ON re.researcherId = r.researcherId
                WHERE r.institutionId = ?
                ORDER BY e.startDate DESC
                """,
                (inst_id,)
            )
            experiments = cursor.fetchall()
            if experiments:
                for exp in experiments:
                    print(f"      Experiment [{exp[0]}] {exp[1]} ({exp[2]} to {exp[3]})")
            else:
                print("      No experiments.")
    else:
        print("No institutions found.")

# researcherId, researcherName, institutionName, contact, experiment count (sort by researcherName)
# experimentId, experimentName, roleName 
def view_researchers(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT r.researcherId, r.researcherName, r.contact, i.institutionName
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        ORDER BY r.researcherName
        """
    )
    researchers = cursor.fetchall()

    print_divider()
    print("Researchers")

    if researchers:
        for res_id, name, contact, institution in researchers:
            cursor.execute(
                """
                SELECT e.experimentId, e.name, ro.roleName
                FROM researcher_experiment re
                JOIN experiment e ON re.experimentId = e.experimentId
                JOIN role ro ON re.roleId = ro.roleId
                WHERE re.researcherId = ?
                ORDER BY e.name
                """,
                (res_id,)
            )
            experiments = cursor.fetchall()
            exp_count = len(experiments)
            print(f"\n  [{res_id}] {name} — {institution} ({contact}) | {exp_count} experiment(s)")
            for exp in experiments:
                print(f"      Experiment [{exp[0]}] {exp[1]} — {exp[2]}")
    else:
        print("No researchers found.")


def view_experiments(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT experimentId, name, startDate, endDate, description
        FROM experiment
        ORDER BY startDate DESC
        """
    )
    experiments = cursor.fetchall()

    print_divider()
    print("Experiments")

    if experiments:
        for exp_id, name, start, end, desc in experiments:
            cursor.execute(
                """
                SELECT fs.fundingSourceId, fs.fundingSourceName, fs.fundingSourceType
                FROM experiment_funding_source efs
                JOIN funding_source fs ON efs.fundingSourceId = fs.fundingSourceId
                WHERE efs.experimentId = ?
                """,
                (exp_id,)
            )
            sources = cursor.fetchall()
            cursor.execute(
                """
                SELECT r.researcherName, ro.roleName
                FROM researcher_experiment re
                JOIN researcher r ON re.researcherId = r.researcherId
                JOIN role ro ON re.roleId = ro.roleId
                WHERE re.experimentId = ?
                ORDER BY r.researcherName
                """,
                (exp_id,)
            )
            researchers = cursor.fetchall()
            print(f"\n  [{exp_id}] {name} ({start} to {end})")
            print(f"      {desc}")
            print(f"      Funding sources ({len(sources)}): {', '.join(s[1] for s in sources) if sources else 'None'}")
            print(f"      Researchers ({len(researchers)}): {', '.join(f'{r[0]} ({r[1]})' for r in researchers) if researchers else 'None'}")
    else:
        print("No experiments found.")


def view_funding_sources(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        "SELECT fundingSourceId, fundingSourceName, fundingSourceType FROM funding_source ORDER BY fundingSourceId"
    )
    rows = cursor.fetchall()

    print_divider()
    print("Funding Sources")

    if rows:
        for row in rows:
            print(row)
    else:
        print("No funding sources found.")


def add_researcher(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Available institutions:")
    cursor.execute("SELECT institutionId, institutionName FROM institution ORDER BY institutionId")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]}")

    try:
        institution_id = int(input("\nEnter institution id: ").strip())
        name = input("Enter researcher name: ").strip()
        contact = input("Enter contact email: ").strip()

        cursor.execute(
            "INSERT INTO researcher (researcherName, contact, institutionId) VALUES (?, ?, ?)",
            (name, contact, institution_id)
        )
        connection.commit()

        print_divider()
        print("Researcher added.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def add_experiment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    try:
        name = input("Enter experiment name: ").strip()
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()
        description = input("Enter description: ").strip()

        cursor.execute(
            "INSERT INTO experiment (name, startDate, endDate, description) VALUES (?, ?, ?, ?)",
            (name, start_date, end_date, description)
        )
        connection.commit()

        print_divider()
        print("Experiment added.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def assign_researcher_to_experiment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Researchers:")
    cursor.execute("SELECT researcherId, researcherName FROM researcher ORDER BY researcherName")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]}")

    print("\nExperiments:")
    cursor.execute("SELECT experimentId, name FROM experiment ORDER BY name")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]}")

    print("\nRoles:")
    cursor.execute("SELECT roleId, roleName FROM role ORDER BY roleId")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]}")

    try:
        researcher_id = int(input("\nEnter researcher id: ").strip())
        experiment_id = int(input("Enter experiment id: ").strip())
        role_id = int(input("Enter role id: ").strip())

        cursor.execute(
            "INSERT INTO researcher_experiment (researcherId, experimentId, roleId) VALUES (?, ?, ?)",
            (researcher_id, experiment_id, role_id)
        )
        connection.commit()

        print_divider()
        print("Researcher assigned to experiment.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def remove_researcher(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Researchers:")
    cursor.execute(
        """
        SELECT r.researcherId, r.researcherName, i.institutionName
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        ORDER BY r.researcherName
        """
    )
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]} ({row[2]})")

    try:
        researcher_id = int(input("\nEnter researcher id to remove: ").strip())

        cursor.execute("DELETE FROM researcher WHERE researcherId = ?", (researcher_id,))
        connection.commit()

        print_divider()
        if cursor.rowcount == 0:
            print("No researcher found.")
        else:
            print("Researcher removed.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def remove_experiment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Experiments:")
    cursor.execute("SELECT experimentId, name, startDate, endDate FROM experiment ORDER BY name")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]} ({row[2]} to {row[3]})")

    try:
        experiment_id = int(input("\nEnter experiment id to remove: ").strip())

        cursor.execute("DELETE FROM experiment WHERE experimentId = ?", (experiment_id,))
        connection.commit()

        print_divider()
        if cursor.rowcount == 0:
            print("No experiment found.")
        else:
            print("Experiment removed.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def unassign_researcher_from_experiment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Current assignments:")
    cursor.execute(
        """
        SELECT r.researcherId, r.researcherName, e.experimentId, e.name, ro.roleName
        FROM researcher_experiment re
        JOIN researcher r ON re.researcherId = r.researcherId
        JOIN experiment e ON re.experimentId = e.experimentId
        JOIN role ro ON re.roleId = ro.roleId
        ORDER BY r.researcherName, e.name
        """
    )
    for row in cursor.fetchall():
        print(f"  Researcher {row[0]} ({row[1]}) — Experiment {row[2]} ({row[3]}) — {row[4]}")

    try:
        researcher_id = int(input("\nEnter researcher id: ").strip())
        experiment_id = int(input("Enter experiment id: ").strip())

        cursor.execute(
            "DELETE FROM researcher_experiment WHERE researcherId = ? AND experimentId = ?",
            (researcher_id, experiment_id)
        )
        connection.commit()

        print_divider()
        if cursor.rowcount == 0:
            print("No assignment found.")
        else:
            print("Researcher unassigned from experiment.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def view_charges(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT c.chargeId, e.name, c.chargeAmount, c.chargeType, c.startDate, c.endDate
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY c.chargeId
        """
    )
    rows = cursor.fetchall()

    print_divider()
    print("Charges")

    if rows:
        for row in rows:
            print(row)
    else:
        print("No charges found.")


def view_charge_adjustments(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        SELECT ca.adjustmentId, c.chargeId, e.name, ca.adjustmentType, ca.amount, ca.adjustmentDate
        FROM charge_adjustment ca
        JOIN charge c ON ca.chargeId = c.chargeId
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY ca.adjustmentDate
        """
    )
    rows = cursor.fetchall()

    print_divider()
    print("Charge Adjustments")

    if rows:
        for row in rows:
            print(f"  [{row[0]}] Charge {row[1]} ({row[2]}) — {row[3]}: ${row[4]:,.2f} on {row[5]}")
        total = sum(row[4] for row in rows)
        print(f"\n  Total adjustments: ${total:,.2f}")
    else:
        print("No charge adjustments found.")


def add_charge(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Experiments:")
    cursor.execute("SELECT experimentId, name FROM experiment ORDER BY name")
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[1]}")

    try:
        experiment_id = int(input("\nEnter experiment id: ").strip())
        charge_amount = float(input("Enter charge amount: ").strip())
        charge_type = input("Enter charge type: ").strip()
        start_date = input("Enter start date (YYYY-MM-DD): ").strip()
        end_date = input("Enter end date (YYYY-MM-DD): ").strip()

        cursor.execute(
            "INSERT INTO charge (experimentId, chargeAmount, chargeType, startDate, endDate) VALUES (?, ?, ?, ?, ?)",
            (experiment_id, charge_amount, charge_type, start_date, end_date)
        )
        connection.commit()

        print_divider()
        print("Charge added.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def add_charge_adjustment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Charges:")
    cursor.execute(
        """
        SELECT c.chargeId, e.name, c.chargeAmount, c.chargeType
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY c.chargeId
        """
    )
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[2]} — {row[3]} ({row[1]})")

    try:
        charge_id = int(input("\nEnter charge id: ").strip())
        adjustment_type = input("Enter adjustment type: ").strip()
        amount = float(input("Enter adjustment amount (use negative for discounts): ").strip())
        adjustment_date = input("Enter adjustment date (YYYY-MM-DD): ").strip()

        cursor.execute(
            "INSERT INTO charge_adjustment (chargeId, adjustmentType, amount, adjustmentDate) VALUES (?, ?, ?, ?)",
            (charge_id, adjustment_type, amount, adjustment_date)
        )
        connection.commit()

        print_divider()
        print("Charge adjustment added.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def remove_charge(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Charges:")
    cursor.execute(
        """
        SELECT c.chargeId, e.name, c.chargeAmount, c.chargeType
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY c.chargeId
        """
    )
    for row in cursor.fetchall():
        print(f"  {row[0]}. {row[2]}: {row[3]} ({row[1]})")

    try:
        charge_id = int(input("\nEnter charge id to remove: ").strip())

        cursor.execute("DELETE FROM charge WHERE chargeId = ?", (charge_id,))
        connection.commit()

        print_divider()
        if cursor.rowcount == 0:
            print("No charge found.")
        else:
            print("Charge removed.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def remove_charge_adjustment(cursor: sqlite3.Cursor, connection: sqlite3.Connection) -> None:
    print_divider()
    print("Charge Adjustments:")
    cursor.execute(
        """
        SELECT ca.adjustmentId, c.chargeId, e.name, ca.adjustmentType, ca.amount, ca.adjustmentDate
        FROM charge_adjustment ca
        JOIN charge c ON ca.chargeId = c.chargeId
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY ca.adjustmentId
        """
    )
    for row in cursor.fetchall():
        print(f"  {row[0]}. Charge {row[1]} ({row[2]}): {row[3]} - {row[4]} on {row[5]}")

    try:
        adjustment_id = int(input("\nEnter adjustment id to remove: ").strip())

        cursor.execute("DELETE FROM charge_adjustment WHERE adjustmentId = ?", (adjustment_id,))
        connection.commit()

        print_divider()
        if cursor.rowcount == 0:
            print("No adjustment found.")
        else:
            print("Charge adjustment removed.")

    except ValueError:
        print_divider()
        print("Invalid input.")
    except sqlite3.IntegrityError as error:
        print_divider()
        print("Database error:", error)


def main() -> None:
    with sqlite3.connect(DB_NAME) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.cursor()

        welcome_screen()

        while True:
            print_menu()
            choice = input("\nChoose an option: ").strip()

            if choice == "1":
                view_institutions(cursor)
                pause()
            elif choice == "2":
                view_researchers(cursor)
                pause()
            elif choice == "3":
                view_experiments(cursor)
                pause()
            elif choice == "4":
                view_funding_sources(cursor)
                pause()
            elif choice == "5":
                view_charges(cursor)
                pause()
            elif choice == "6":
                view_charge_adjustments(cursor)
                pause()
            elif choice == "7":
                add_researcher(cursor, connection)
                pause()
            elif choice == "8":
                add_experiment(cursor, connection)
                pause()
            elif choice == "9":
                assign_researcher_to_experiment(cursor, connection)
                pause()
            elif choice == "10":
                remove_researcher(cursor, connection)
                pause()
            elif choice == "11":
                remove_experiment(cursor, connection)
                pause()
            elif choice == "12":
                unassign_researcher_from_experiment(cursor, connection)
                pause()
            elif choice == "13":
                add_charge(cursor, connection)
                pause()
            elif choice == "14":
                add_charge_adjustment(cursor, connection)
                pause()
            elif choice == "15":
                remove_charge(cursor, connection)
                pause()
            elif choice == "16":
                remove_charge_adjustment(cursor, connection)
                pause()
            elif choice == "17":
                print_divider()
                print("Thank you for using the menu!")
                break
            else:
                print_divider()
                print("Invalid option. Try again.")
                pause()


if __name__ == "__main__":
    main()
