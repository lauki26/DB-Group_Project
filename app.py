from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, g, abort
)
import sqlite3
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = "control-group"

DATABASE = os.path.join(BASE_DIR, "controlgroup.db")


def get_db() -> sqlite3.Connection:
    """One connection per request, stored on Flask's `g` object."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row                          
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql: str, params: tuple = ()) -> list:
    return get_db().execute(sql, params).fetchall()


def query_one(sql: str, params: tuple = ()):
    return get_db().execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur


@app.route("/")
def index():

    spend_by_experiment = query("""
        SELECT
            e.experimentId,
            e.name,
            COALESCE(
                (SELECT SUM(chargeAmount) FROM charge WHERE experimentId = e.experimentId),
                0
            ) +
            COALESCE(
                (SELECT SUM(ca.amount)
                 FROM charge_adjustment ca
                 JOIN charge c ON ca.chargeId = c.chargeId
                 WHERE c.experimentId = e.experimentId),
                0
            ) AS net_spend
        FROM experiment e
        ORDER BY net_spend DESC
        LIMIT 6
    """)
    max_spend = max((r["net_spend"] for r in spend_by_experiment), default=0)


    funding_mix = query("""
        SELECT fs.fundingSourceType AS type, COUNT(*) AS count
        FROM experiment_funding_source efs
        JOIN funding_source fs ON efs.fundingSourceId = fs.fundingSourceId
        GROUP BY fs.fundingSourceType
        ORDER BY count DESC
    """)
    max_funding = max((r["count"] for r in funding_mix), default=0)
    total_funding_links = sum(r["count"] for r in funding_mix)


    top_researchers = query("""
        SELECT
            r.researcherId,
            r.researcherName,
            i.institutionName,
            COUNT(re.experimentId) AS exp_count
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        LEFT JOIN researcher_experiment re ON re.researcherId = r.researcherId
        GROUP BY r.researcherId
        ORDER BY exp_count DESC, r.researcherName
        LIMIT 5
    """)


    recent_activity = query("""
        SELECT * FROM (
            SELECT
                'Charge' AS kind, c.chargeId AS id, c.startDate AS date,
                c.chargeAmount AS amount, c.chargeType AS subtype,
                e.name AS experiment_name, e.experimentId AS exp_id
            FROM charge c
            JOIN experiment e ON c.experimentId = e.experimentId
            UNION ALL
            SELECT
                'Adjustment', ca.adjustmentId, ca.adjustmentDate, ca.amount,
                ca.adjustmentType, e.name, e.experimentId
            FROM charge_adjustment ca
            JOIN charge c ON ca.chargeId = c.chargeId
            JOIN experiment e ON c.experimentId = e.experimentId
        )
        ORDER BY date DESC, kind
        LIMIT 7
    """)

    return render_template(
        "index.html",
        spend_by_experiment=spend_by_experiment,
        max_spend=max_spend,
        funding_mix=funding_mix,
        max_funding=max_funding,
        total_funding_links=total_funding_links,
        top_researchers=top_researchers,
        recent_activity=recent_activity,
    )


@app.route("/institutions")
def institutions():
    type_filter = request.args.get("type", "").strip()
    search = request.args.get("q", "").strip()

    sql = """
        SELECT i.institutionId, i.institutionName, i.institutionType,
               COUNT(r.researcherId) AS researcher_count
        FROM institution i
        LEFT JOIN researcher r ON r.institutionId = i.institutionId
        WHERE 1=1
    """
    params = []
    if type_filter:
        sql += " AND i.institutionType = ?"
        params.append(type_filter)
    if search:
        sql += " AND i.institutionName LIKE ?"
        params.append(f"%{search}%")
    sql += " GROUP BY i.institutionId ORDER BY i.institutionName"

    rows = query(sql, tuple(params))
    types = [r["institutionType"] for r in query(
        "SELECT DISTINCT institutionType FROM institution ORDER BY institutionType"
    )]

    return render_template(
        "institutions.html",
        institutions=rows,
        types=types,
        type_filter=type_filter,
        search=search,
    )


@app.route("/institutions/<int:inst_id>")
def institution_detail(inst_id):
    inst = query_one(
        "SELECT * FROM institution WHERE institutionId = ?", (inst_id,)
    )
    if not inst:
        abort(404)

    researchers = query("""
        SELECT researcherId, researcherName, contact
        FROM researcher
        WHERE institutionId = ?
        ORDER BY researcherName
    """, (inst_id,))

    experiments = query("""
        SELECT DISTINCT e.experimentId, e.name, e.startDate, e.endDate
        FROM experiment e
        JOIN researcher_experiment re ON e.experimentId = re.experimentId
        JOIN researcher r ON re.researcherId = r.researcherId
        WHERE r.institutionId = ?
        ORDER BY e.startDate DESC
    """, (inst_id,))

    return render_template(
        "institution_detail.html",
        institution=inst,
        researchers=researchers,
        experiments=experiments,
    )


@app.route("/institutions/new", methods=["GET", "POST"])
def institution_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        inst_type = request.form.get("type", "").strip()
        if not (name and inst_type):
            flash("All fields are required.", "error")
        else:
            try:
                cur = execute(
                    "INSERT INTO institution (institutionName, institutionType) VALUES (?, ?)",
                    (name, inst_type),
                )
                flash(f"Added institution: {name}", "success")
                return redirect(url_for("institution_detail", inst_id=cur.lastrowid))
            except sqlite3.IntegrityError as err:
                flash(f"Could not add institution: {err}", "error")

    existing_types = [r["institutionType"] for r in query(
        "SELECT DISTINCT institutionType FROM institution ORDER BY institutionType"
    )]
    return render_template("institution_form.html", record=None, existing_types=existing_types)


@app.route("/institutions/<int:inst_id>/edit", methods=["GET", "POST"])
def institution_edit(inst_id):
    inst = query_one("SELECT * FROM institution WHERE institutionId = ?", (inst_id,))
    if not inst:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        inst_type = request.form.get("type", "").strip()
        if not (name and inst_type):
            flash("All fields are required.", "error")
        else:
            try:
                execute(
                    "UPDATE institution SET institutionName = ?, institutionType = ? WHERE institutionId = ?",
                    (name, inst_type, inst_id),
                )
                flash(f"Updated institution: {name}", "success")
                return redirect(url_for("institution_detail", inst_id=inst_id))
            except sqlite3.IntegrityError as err:
                flash(f"Could not update institution: {err}", "error")

    existing_types = [r["institutionType"] for r in query(
        "SELECT DISTINCT institutionType FROM institution ORDER BY institutionType"
    )]
    return render_template("institution_form.html", record=inst, existing_types=existing_types)


@app.route("/institutions/<int:inst_id>/delete", methods=["POST"])
def institution_delete(inst_id):
    inst = query_one("SELECT institutionName FROM institution WHERE institutionId = ?", (inst_id,))
    if not inst:
        abort(404)
    researcher_count = query_one(
        "SELECT COUNT(*) AS c FROM researcher WHERE institutionId = ?", (inst_id,)
    )["c"]
    if researcher_count > 0:
        flash(
            f"Cannot delete {inst['institutionName']}: {researcher_count} researcher(s) still affiliated. "
            "Reassign or remove them first.",
            "error",
        )
        return redirect(url_for("institution_detail", inst_id=inst_id))
    try:
        execute("DELETE FROM institution WHERE institutionId = ?", (inst_id,))
        flash(f"Removed institution: {inst['institutionName']}", "success")
        return redirect(url_for("institutions"))
    except sqlite3.IntegrityError as err:
        flash(f"Could not remove institution: {err}", "error")
        return redirect(url_for("institution_detail", inst_id=inst_id))


@app.route("/researchers")
def researchers():
    search = request.args.get("q", "").strip()
    inst_filter = request.args.get("institution", "").strip()

    sql = """
        SELECT r.researcherId, r.researcherName, r.contact,
               i.institutionId, i.institutionName,
               COUNT(re.experimentId) AS experiment_count
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        LEFT JOIN researcher_experiment re ON re.researcherId = r.researcherId
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (r.researcherName LIKE ? OR r.contact LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if inst_filter:
        sql += " AND i.institutionId = ?"
        params.append(inst_filter)
    sql += " GROUP BY r.researcherId ORDER BY r.researcherName"

    rows = query(sql, tuple(params))
    institutions_list = query(
        "SELECT institutionId, institutionName FROM institution ORDER BY institutionName"
    )

    return render_template(
        "researchers.html",
        researchers=rows,
        institutions=institutions_list,
        search=search,
        inst_filter=inst_filter,
    )


@app.route("/researchers/<int:res_id>")
def researcher_detail(res_id):
    res = query_one("""
        SELECT r.*, i.institutionName, i.institutionId
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        WHERE r.researcherId = ?
    """, (res_id,))
    if not res:
        abort(404)

    assignments = query("""
        SELECT e.experimentId, e.name, e.startDate, e.endDate, ro.roleName
        FROM researcher_experiment re
        JOIN experiment e ON re.experimentId = e.experimentId
        JOIN role ro ON re.roleId = ro.roleId
        WHERE re.researcherId = ?
        ORDER BY e.startDate DESC
    """, (res_id,))

    return render_template(
        "researcher_detail.html",
        researcher=res,
        assignments=assignments,
    )


@app.route("/researchers/new", methods=["GET", "POST"])
def researcher_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        institution_id = request.form.get("institution_id", "").strip()

        if not (name and contact and institution_id):
            flash("All fields are required.", "error")
        else:
            try:
                execute(
                    "INSERT INTO researcher (researcherName, contact, institutionId) VALUES (?, ?, ?)",
                    (name, contact, int(institution_id)),
                )
                flash(f"Added researcher: {name}", "success")
                return redirect(url_for("researchers"))
            except (sqlite3.IntegrityError, ValueError) as err:
                flash(f"Could not add researcher: {err}", "error")

    institutions_list = query(
        "SELECT institutionId, institutionName FROM institution ORDER BY institutionName"
    )
    return render_template("researcher_form.html", institutions=institutions_list, record=None)


@app.route("/researchers/<int:res_id>/edit", methods=["GET", "POST"])
def researcher_edit(res_id):
    res = query_one("SELECT * FROM researcher WHERE researcherId = ?", (res_id,))
    if not res:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        contact = request.form.get("contact", "").strip()
        institution_id = request.form.get("institution_id", "").strip()

        if not (name and contact and institution_id):
            flash("All fields are required.", "error")
        else:
            try:
                execute(
                    "UPDATE researcher SET researcherName = ?, contact = ?, institutionId = ? WHERE researcherId = ?",
                    (name, contact, int(institution_id), res_id),
                )
                flash(f"Updated researcher: {name}", "success")
                return redirect(url_for("researcher_detail", res_id=res_id))
            except (sqlite3.IntegrityError, ValueError) as err:
                flash(f"Could not update researcher: {err}", "error")

    institutions_list = query(
        "SELECT institutionId, institutionName FROM institution ORDER BY institutionName"
    )
    return render_template("researcher_form.html", institutions=institutions_list, record=res)


@app.route("/researchers/<int:res_id>/delete", methods=["POST"])
def researcher_delete(res_id):
    res = query_one("SELECT researcherName FROM researcher WHERE researcherId = ?", (res_id,))
    if not res:
        abort(404)
    try:

        execute("DELETE FROM researcher_experiment WHERE researcherId = ?", (res_id,))
        execute("DELETE FROM researcher WHERE researcherId = ?", (res_id,))
        flash(f"Removed researcher: {res['researcherName']}", "success")
    except sqlite3.IntegrityError as err:
        flash(f"Could not remove researcher: {err}", "error")
    return redirect(url_for("researchers"))


@app.route("/experiments")
def experiments():
    search = request.args.get("q", "").strip()
    start_after = request.args.get("start_after", "").strip()
    end_before = request.args.get("end_before", "").strip()

    sql = """
        SELECT experimentId, name, startDate, endDate, description
        FROM experiment
        WHERE 1=1
    """
    params = []
    if search:
        sql += " AND (name LIKE ? OR description LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    if start_after:
        sql += " AND startDate >= ?"
        params.append(start_after)
    if end_before:
        sql += " AND endDate <= ?"
        params.append(end_before)
    sql += " ORDER BY startDate DESC"

    rows = query(sql, tuple(params))
    return render_template(
        "experiments.html",
        experiments=rows,
        search=search,
        start_after=start_after,
        end_before=end_before,
    )


@app.route("/experiments/<int:exp_id>")
def experiment_detail(exp_id):
    exp = query_one("SELECT * FROM experiment WHERE experimentId = ?", (exp_id,))
    if not exp:
        abort(404)

    researchers_on = query("""
        SELECT r.researcherId, r.researcherName, ro.roleName, i.institutionName
        FROM researcher_experiment re
        JOIN researcher r ON re.researcherId = r.researcherId
        JOIN role ro ON re.roleId = ro.roleId
        JOIN institution i ON r.institutionId = i.institutionId
        WHERE re.experimentId = ?
        ORDER BY r.researcherName
    """, (exp_id,))

    funding = query("""
        SELECT fs.fundingSourceId, fs.fundingSourceName, fs.fundingSourceType
        FROM experiment_funding_source efs
        JOIN funding_source fs ON efs.fundingSourceId = fs.fundingSourceId
        WHERE efs.experimentId = ?
        ORDER BY fs.fundingSourceName
    """, (exp_id,))

    charges = query("""
        SELECT chargeId, chargeAmount, chargeType, startDate, endDate
        FROM charge
        WHERE experimentId = ?
        ORDER BY startDate DESC
    """, (exp_id,))

    adjustments = query("""
        SELECT ca.adjustmentId, ca.chargeId, ca.adjustmentType, ca.amount, ca.adjustmentDate
        FROM charge_adjustment ca
        JOIN charge c ON ca.chargeId = c.chargeId
        WHERE c.experimentId = ?
        ORDER BY ca.adjustmentDate DESC
    """, (exp_id,))

    total_charges = sum(c["chargeAmount"] for c in charges)
    total_adjust = sum(a["amount"] for a in adjustments)


    available_researchers = query("""
        SELECT r.researcherId, r.researcherName, i.institutionName
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        WHERE r.researcherId NOT IN (
            SELECT researcherId FROM researcher_experiment WHERE experimentId = ?
        )
        ORDER BY r.researcherName
    """, (exp_id,))
    roles = query("SELECT roleId, roleName FROM role ORDER BY roleId")

    available_funding = query("""
        SELECT fundingSourceId, fundingSourceName, fundingSourceType
        FROM funding_source
        WHERE fundingSourceId NOT IN (
            SELECT fundingSourceId FROM experiment_funding_source WHERE experimentId = ?
        )
        ORDER BY fundingSourceName
    """, (exp_id,))

    return render_template(
        "experiment_detail.html",
        experiment=exp,
        researchers_on=researchers_on,
        funding=funding,
        charges=charges,
        adjustments=adjustments,
        total_charges=total_charges,
        total_adjust=total_adjust,
        net_total=total_charges + total_adjust,
        available_researchers=available_researchers,
        roles=roles,
        available_funding=available_funding,
    )


@app.route("/experiments/new", methods=["GET", "POST"])
def experiment_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        description = request.form.get("description", "").strip()

        if not (name and start_date and end_date and description):
            flash("All fields are required.", "error")
        else:
            try:
                cur = execute(
                    "INSERT INTO experiment (name, startDate, endDate, description) VALUES (?, ?, ?, ?)",
                    (name, start_date, end_date, description),
                )
                flash(f"Added experiment: {name}", "success")
                return redirect(url_for("experiment_detail", exp_id=cur.lastrowid))
            except sqlite3.IntegrityError as err:
                flash(f"Could not add experiment: {err}", "error")

    return render_template("experiment_form.html", record=None)


@app.route("/experiments/<int:exp_id>/edit", methods=["GET", "POST"])
def experiment_edit(exp_id):
    exp = query_one("SELECT * FROM experiment WHERE experimentId = ?", (exp_id,))
    if not exp:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        start_date = request.form.get("start_date", "").strip()
        end_date = request.form.get("end_date", "").strip()
        description = request.form.get("description", "").strip()

        if not (name and start_date and end_date and description):
            flash("All fields are required.", "error")
        else:
            try:
                execute(
                    "UPDATE experiment SET name = ?, startDate = ?, endDate = ?, description = ? WHERE experimentId = ?",
                    (name, start_date, end_date, description, exp_id),
                )
                flash(f"Updated experiment: {name}", "success")
                return redirect(url_for("experiment_detail", exp_id=exp_id))
            except sqlite3.IntegrityError as err:
                flash(f"Could not update experiment: {err}", "error")

    return render_template("experiment_form.html", record=exp)


@app.route("/experiments/<int:exp_id>/delete", methods=["POST"])
def experiment_delete(exp_id):
    exp = query_one("SELECT name FROM experiment WHERE experimentId = ?", (exp_id,))
    if not exp:
        abort(404)
    try:

        execute("""DELETE FROM charge_adjustment WHERE chargeId IN
                   (SELECT chargeId FROM charge WHERE experimentId = ?)""", (exp_id,))
        execute("DELETE FROM charge WHERE experimentId = ?", (exp_id,))
        execute("DELETE FROM researcher_experiment WHERE experimentId = ?", (exp_id,))
        execute("DELETE FROM experiment_funding_source WHERE experimentId = ?", (exp_id,))
        execute("DELETE FROM experiment WHERE experimentId = ?", (exp_id,))
        flash(f"Removed experiment: {exp['name']}", "success")
    except sqlite3.IntegrityError as err:
        flash(f"Could not remove experiment: {err}", "error")
    return redirect(url_for("experiments"))


@app.route("/experiments/<int:exp_id>/assign", methods=["POST"])
def experiment_assign(exp_id):
    res_id = request.form.get("researcher_id", "").strip()
    role_id = request.form.get("role_id", "").strip()
    if not (res_id and role_id):
        flash("Pick a researcher and a role.", "error")
    else:
        try:
            execute(
                "INSERT INTO researcher_experiment (researcherId, experimentId, roleId) VALUES (?, ?, ?)",
                (int(res_id), exp_id, int(role_id)),
            )
            flash("Researcher assigned.", "success")
        except (sqlite3.IntegrityError, ValueError) as err:
            flash(f"Could not assign: {err}", "error")
    return redirect(url_for("experiment_detail", exp_id=exp_id))


@app.route("/experiments/<int:exp_id>/unassign/<int:res_id>", methods=["POST"])
def experiment_unassign(exp_id, res_id):
    execute(
        "DELETE FROM researcher_experiment WHERE researcherId = ? AND experimentId = ?",
        (res_id, exp_id),
    )
    flash("Researcher unassigned.", "success")
    return redirect(url_for("experiment_detail", exp_id=exp_id))


@app.route("/calendar")
def calendar_view():
    import calendar as cal
    from datetime import date, timedelta

    today = date.today()
    try:
        year = int(request.args.get("year", today.year))
        month = int(request.args.get("month", today.month))
        if not (1 <= month <= 12):
            raise ValueError
    except (TypeError, ValueError):
        year, month = today.year, today.month

    first_day = date(year, month, 1)
    days_in_month = cal.monthrange(year, month)[1]
    last_day = date(year, month, days_in_month)

    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    grid_start = first_day - timedelta(days=first_day.weekday())
    grid_end_target = last_day + timedelta(days=(6 - last_day.weekday()))
    while (grid_end_target - grid_start).days < 41:
        grid_end_target += timedelta(days=7)
    grid_end = grid_end_target

    weeks = []
    cursor = grid_start
    while cursor <= grid_end:
        week = []
        for _ in range(7):
            week.append({
                "date": cursor,
                "in_month": cursor.month == month,
                "is_today": cursor == today,
                "iso": cursor.isoformat(),
                "day": cursor.day,
            })
            cursor += timedelta(days=1)
        weeks.append(week)

    visible_start = grid_start.isoformat()
    visible_end = grid_end.isoformat()
    experiments_in_view = query("""
        SELECT experimentId, name, startDate, endDate, description
        FROM experiment
        WHERE NOT (endDate < ? OR startDate > ?)
        ORDER BY startDate, experimentId
    """, (visible_start, visible_end))

    def parse_iso(s):
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))

    rows = []
    for exp in experiments_in_view:
        try:
            s_date = parse_iso(exp["startDate"])
            e_date = parse_iso(exp["endDate"])
        except ValueError:
            continue
        bar_start = max(s_date, grid_start)
        bar_end = min(e_date, grid_end)
        if bar_end < bar_start:
            continue

        placed = False
        for row in rows:
            if all(bar_end < b["start"] or bar_start > b["end"] for b in row):
                row.append({
                    "exp_id": exp["experimentId"],
                    "name": exp["name"],
                    "start": bar_start,
                    "end": bar_end,
                    "real_start": s_date,
                    "real_end": e_date,
                    "starts_before_view": s_date < grid_start,
                    "ends_after_view": e_date > grid_end,
                })
                placed = True
                break
        if not placed:
            rows.append([{
                "exp_id": exp["experimentId"],
                "name": exp["name"],
                "start": bar_start,
                "end": bar_end,
                "real_start": s_date,
                "real_end": e_date,
                "starts_before_view": s_date < grid_start,
                "ends_after_view": e_date > grid_end,
            }])

    week_bars = []
    for week in weeks:
        wk_start = week[0]["date"]
        wk_end = week[6]["date"]
        wk_rows = []
        for row in rows:
            for bar in row:
                if bar["end"] < wk_start or bar["start"] > wk_end:
                    continue
                seg_start = max(bar["start"], wk_start)
                seg_end = min(bar["end"], wk_end)
                start_col = (seg_start - wk_start).days
                span = (seg_end - seg_start).days + 1
                wk_rows.append({
                    "exp_id": bar["exp_id"],
                    "name": bar["name"],
                    "start_col": start_col,
                    "span": span,
                    "color_idx": bar["exp_id"] % 6,
                    "real_start": bar["real_start"],
                    "real_end": bar["real_end"],
                    "continues_left": seg_start > bar["real_start"] or bar["starts_before_view"],
                    "continues_right": seg_end < bar["real_end"] or bar["ends_after_view"],
                })
        wk_rows.sort(key=lambda b: (b["start_col"], -b["span"]))
        week_bars.append(wk_rows)

    conflicts = query("""
        SELECT
            r.researcherId,
            r.researcherName,
            e1.experimentId AS exp1_id,
            e1.name AS exp1_name,
            e1.startDate AS exp1_start,
            e1.endDate AS exp1_end,
            e2.experimentId AS exp2_id,
            e2.name AS exp2_name,
            e2.startDate AS exp2_start,
            e2.endDate AS exp2_end
        FROM researcher r
        JOIN researcher_experiment re1 ON re1.researcherId = r.researcherId
        JOIN experiment e1 ON re1.experimentId = e1.experimentId
        JOIN researcher_experiment re2 ON re2.researcherId = r.researcherId
        JOIN experiment e2 ON re2.experimentId = e2.experimentId
        WHERE e1.experimentId < e2.experimentId
          AND NOT (e1.endDate < e2.startDate OR e1.startDate > e2.endDate)
        ORDER BY r.researcherName, e1.startDate
    """)

    today_iso = today.isoformat()
    in_30 = (today + timedelta(days=30)).isoformat()
    in_14 = (today + timedelta(days=14)).isoformat()
    starting_soon = query("""
        SELECT experimentId, name, startDate, endDate
        FROM experiment
        WHERE startDate >= ? AND startDate <= ?
        ORDER BY startDate
        LIMIT 6
    """, (today_iso, in_30))
    ending_soon = query("""
        SELECT experimentId, name, startDate, endDate
        FROM experiment
        WHERE endDate >= ? AND endDate <= ?
        ORDER BY endDate
        LIMIT 6
    """, (today_iso, in_14))

    currently_active_count = query_one("""
        SELECT COUNT(*) AS c FROM experiment
        WHERE startDate <= ? AND endDate >= ?
    """, (today_iso, today_iso))["c"]

    month_label = first_day.strftime("%B %Y")

    return render_template(
        "calendar.html",
        weeks=weeks,
        week_bars=week_bars,
        month_label=month_label,
        year=year,
        month=month,
        prev_year=prev_year, prev_month=prev_month,
        next_year=next_year, next_month=next_month,
        today=today,
        today_year=today.year, today_month=today.month,
        conflicts=conflicts,
        starting_soon=starting_soon,
        ending_soon=ending_soon,
        currently_active_count=currently_active_count,
        total_in_view=len(experiments_in_view),
    )


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return render_template("search.html", q="", results=None, total=0)

    like = f"%{q}%"

    institutions_hits = query("""
        SELECT institutionId, institutionName, institutionType
        FROM institution
        WHERE institutionName LIKE ? OR institutionType LIKE ?
        ORDER BY institutionName
    """, (like, like))

    researchers_hits = query("""
        SELECT r.researcherId, r.researcherName, r.contact,
               i.institutionId, i.institutionName
        FROM researcher r
        JOIN institution i ON r.institutionId = i.institutionId
        WHERE r.researcherName LIKE ? OR r.contact LIKE ?
        ORDER BY r.researcherName
    """, (like, like))

    experiments_hits = query("""
        SELECT experimentId, name, description, startDate, endDate
        FROM experiment
        WHERE name LIKE ? OR description LIKE ?
        ORDER BY startDate DESC
    """, (like, like))

    funding_hits = query("""
        SELECT fundingSourceId, fundingSourceName, fundingSourceType
        FROM funding_source
        WHERE fundingSourceName LIKE ? OR fundingSourceType LIKE ?
        ORDER BY fundingSourceName
    """, (like, like))

    charges_hits = query("""
        SELECT c.chargeId, c.chargeAmount, c.chargeType, c.startDate, c.endDate,
               e.experimentId, e.name AS experimentName
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        WHERE c.chargeType LIKE ?
        ORDER BY c.startDate DESC
    """, (like,))

    equipment_hits = query("""
        SELECT
            ee.equipmentUsageId,
            eq.equipmentName,
            eq.equipmentPurpose,
            e.experimentId,
            e.name AS experimentName
        FROM experiment_equipment ee
        JOIN equipment eq ON ee.equipmentId = eq.equipmentId
        JOIN experiment e ON ee.experimentId = e.experimentId
        WHERE
            eq.equipmentName LIKE ?
            OR eq.equipmentPurpose LIKE ?
            OR e.name LIKE ?
        ORDER BY eq.equipmentName
    """, (like, like, like))

    facilities_hits = query("""
        SELECT
            ef.facilityUsageId,
            f.facilityName,
            f.facilityType,
            e.experimentId,
            e.name AS experimentName
        FROM experiment_facility ef
        JOIN facility f ON ef.facilityId = f.facilityId
        JOIN experiment e ON ef.experimentId = e.experimentId
        WHERE
            f.facilityName LIKE ?
            OR f.facilityType LIKE ?
            OR e.name LIKE ?
        ORDER BY f.facilityName
    """, (like, like, like))

    results = {
        "institutions": institutions_hits,
        "researchers":  researchers_hits,
        "experiments":  experiments_hits,
        "funding":      funding_hits,
        "charges":      charges_hits,
        "equipment":    equipment_hits,
        "facilities":   facilities_hits,
    }
    
    total = sum(len(v) for v in results.values())

    return render_template("search.html", q=q, results=results, total=total)


@app.route("/funding-sources")
def funding_sources():
    type_filter = request.args.get("type", "").strip()
    sql = """
        SELECT fs.fundingSourceId, fs.fundingSourceName, fs.fundingSourceType,
               COUNT(efs.experimentId) AS experiment_count
        FROM funding_source fs
        LEFT JOIN experiment_funding_source efs ON efs.fundingSourceId = fs.fundingSourceId
        WHERE 1=1
    """
    params = []
    if type_filter:
        sql += " AND fs.fundingSourceType = ?"
        params.append(type_filter)
    sql += " GROUP BY fs.fundingSourceId ORDER BY fs.fundingSourceName"

    rows = query(sql, tuple(params))
    types = [r["fundingSourceType"] for r in query(
        "SELECT DISTINCT fundingSourceType FROM funding_source ORDER BY fundingSourceType"
    )]
    return render_template(
        "funding_sources.html",
        funding_sources=rows,
        types=types,
        type_filter=type_filter,
    )


@app.route("/funding-sources/<int:fs_id>")
def funding_source_detail(fs_id):
    source = query_one(
        "SELECT * FROM funding_source WHERE fundingSourceId = ?", (fs_id,)
    )
    if not source:
        abort(404)

    experiments = query("""
        SELECT e.experimentId, e.name, e.startDate, e.endDate,
               COALESCE(
                   (SELECT SUM(chargeAmount) FROM charge WHERE experimentId = e.experimentId),
                   0
               ) AS total_charges,
               COALESCE(
                   (SELECT SUM(ca.amount)
                    FROM charge_adjustment ca
                    JOIN charge c ON ca.chargeId = c.chargeId
                    WHERE c.experimentId = e.experimentId),
                   0
               ) AS total_adjustments
        FROM experiment_funding_source efs
        JOIN experiment e ON efs.experimentId = e.experimentId
        WHERE efs.fundingSourceId = ?
        ORDER BY e.startDate DESC
    """, (fs_id,))

    other_sources = query("""
        SELECT DISTINCT fs.fundingSourceId, fs.fundingSourceName, fs.fundingSourceType
        FROM experiment_funding_source efs
        JOIN funding_source fs ON efs.fundingSourceId = fs.fundingSourceId
        WHERE efs.experimentId IN (
            SELECT experimentId FROM experiment_funding_source WHERE fundingSourceId = ?
        )
        AND fs.fundingSourceId != ?
        ORDER BY fs.fundingSourceName
    """, (fs_id, fs_id))

    total_funded = sum(e["total_charges"] + e["total_adjustments"] for e in experiments)

    return render_template(
        "funding_source_detail.html",
        source=source,
        experiments=experiments,
        other_sources=other_sources,
        total_funded=total_funded,
    )


@app.route("/funding-sources/new", methods=["GET", "POST"])
def funding_source_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        fs_type = request.form.get("type", "").strip()

        if not (name and fs_type):
            flash("All fields are required.", "error")
        else:
            try:
                cur = execute(
                    "INSERT INTO funding_source (fundingSourceName, fundingSourceType) VALUES (?, ?)",
                    (name, fs_type),
                )
                flash(f"Added funding source: {name}", "success")
                return redirect(url_for("funding_source_detail", fs_id=cur.lastrowid))
            except sqlite3.IntegrityError as err:
                flash(f"Could not add funding source: {err}", "error")

    existing_types = [r["fundingSourceType"] for r in query(
        "SELECT DISTINCT fundingSourceType FROM funding_source ORDER BY fundingSourceType"
    )]
    return render_template("funding_source_form.html", existing_types=existing_types, record=None)


@app.route("/funding-sources/<int:fs_id>/edit", methods=["GET", "POST"])
def funding_source_edit(fs_id):
    src = query_one("SELECT * FROM funding_source WHERE fundingSourceId = ?", (fs_id,))
    if not src:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        fs_type = request.form.get("type", "").strip()
        if not (name and fs_type):
            flash("All fields are required.", "error")
        else:
            try:
                execute(
                    "UPDATE funding_source SET fundingSourceName = ?, fundingSourceType = ? WHERE fundingSourceId = ?",
                    (name, fs_type, fs_id),
                )
                flash(f"Updated funding source: {name}", "success")
                return redirect(url_for("funding_source_detail", fs_id=fs_id))
            except sqlite3.IntegrityError as err:
                flash(f"Could not update funding source: {err}", "error")

    existing_types = [r["fundingSourceType"] for r in query(
        "SELECT DISTINCT fundingSourceType FROM funding_source ORDER BY fundingSourceType"
    )]
    return render_template("funding_source_form.html", existing_types=existing_types, record=src)


@app.route("/funding-sources/<int:fs_id>/delete", methods=["POST"])
def funding_source_delete(fs_id):
    src = query_one("SELECT fundingSourceName FROM funding_source WHERE fundingSourceId = ?", (fs_id,))
    if not src:
        abort(404)
    linked = query_one(
        "SELECT COUNT(*) AS c FROM experiment_funding_source WHERE fundingSourceId = ?", (fs_id,)
    )["c"]
    if linked > 0:
        flash(
            f"Cannot delete {src['fundingSourceName']}: still linked to {linked} experiment(s). "
            "Unlink them first from each experiment's detail page.",
            "error",
        )
        return redirect(url_for("funding_source_detail", fs_id=fs_id))
    try:
        execute("DELETE FROM funding_source WHERE fundingSourceId = ?", (fs_id,))
        flash(f"Removed funding source: {src['fundingSourceName']}", "success")
        return redirect(url_for("funding_sources"))
    except sqlite3.IntegrityError as err:
        flash(f"Could not remove funding source: {err}", "error")
        return redirect(url_for("funding_source_detail", fs_id=fs_id))


@app.route("/experiments/<int:exp_id>/funding/link", methods=["POST"])
def experiment_funding_link(exp_id):
    fs_id = request.form.get("funding_source_id", "").strip()
    if not fs_id:
        flash("Pick a funding source.", "error")
    else:
        try:
            execute(
                "INSERT INTO experiment_funding_source (experimentId, fundingSourceId) VALUES (?, ?)",
                (exp_id, int(fs_id)),
            )
            flash("Funding source linked.", "success")
        except (sqlite3.IntegrityError, ValueError) as err:
            flash(f"Could not link funding source: {err}", "error")
    return redirect(url_for("experiment_detail", exp_id=exp_id))


@app.route("/experiments/<int:exp_id>/funding/<int:fs_id>/unlink", methods=["POST"])
def experiment_funding_unlink(exp_id, fs_id):
    execute(
        "DELETE FROM experiment_funding_source WHERE experimentId = ? AND fundingSourceId = ?",
        (exp_id, fs_id),
    )
    flash("Funding source removed.", "success")
    return redirect(url_for("experiment_detail", exp_id=exp_id))


@app.route("/charges")
def charges():
    exp_filter = request.args.get("experiment", "").strip()
    type_filter = request.args.get("type", "").strip()
    search = request.args.get("q", "").strip()

    sql = """
        SELECT c.chargeId, c.chargeAmount, c.chargeType, c.startDate, c.endDate,
               e.experimentId, e.name AS experimentName,
               (SELECT COALESCE(SUM(amount), 0) FROM charge_adjustment WHERE chargeId = c.chargeId) AS adjustments_total
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        WHERE 1=1
    """
    params = []
    if exp_filter:
        sql += " AND e.experimentId = ?"
        params.append(exp_filter)
    if type_filter:
        sql += " AND c.chargeType = ?"
        params.append(type_filter)
    if search:
        sql += " AND (c.chargeType LIKE ? OR e.name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    sql += " ORDER BY c.startDate DESC"

    rows = query(sql, tuple(params))
    experiments_list = query("SELECT experimentId, name FROM experiment ORDER BY name")
    types = [r["chargeType"] for r in query(
        "SELECT DISTINCT chargeType FROM charge ORDER BY chargeType"
    )]

    total = sum(r["chargeAmount"] for r in rows)
    total_adj = sum(r["adjustments_total"] for r in rows)

    return render_template(
        "charges.html",
        charges=rows,
        experiments=experiments_list,
        types=types,
        exp_filter=exp_filter,
        type_filter=type_filter,
        search=search,
        total=total,
        total_adj=total_adj,
    )


@app.route("/charges/new", methods=["GET", "POST"])
def charge_new():
    if request.method == "POST":
        try:
            execute(
                """INSERT INTO charge (experimentId, chargeAmount, chargeType, startDate, endDate)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    int(request.form["experiment_id"]),
                    float(request.form["amount"]),
                    request.form["charge_type"].strip(),
                    request.form["start_date"].strip(),
                    request.form["end_date"].strip(),
                ),
            )
            flash("Charge added.", "success")
            return redirect(url_for("charges"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not add charge: {err}", "error")

    experiments_list = query("SELECT experimentId, name FROM experiment ORDER BY name")
    preselect = request.args.get("experiment", "")
    return render_template(
        "charge_form.html",
        experiments=experiments_list,
        preselect=preselect,
        record=None,
    )


@app.route("/charges/<int:charge_id>/edit", methods=["GET", "POST"])
def charge_edit(charge_id):
    ch = query_one("SELECT * FROM charge WHERE chargeId = ?", (charge_id,))
    if not ch:
        abort(404)
    if request.method == "POST":
        try:
            execute(
                """UPDATE charge SET experimentId = ?, chargeAmount = ?, chargeType = ?,
                                     startDate = ?, endDate = ? WHERE chargeId = ?""",
                (
                    int(request.form["experiment_id"]),
                    float(request.form["amount"]),
                    request.form["charge_type"].strip(),
                    request.form["start_date"].strip(),
                    request.form["end_date"].strip(),
                    charge_id,
                ),
            )
            flash("Charge updated.", "success")
            return redirect(url_for("charges"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not update charge: {err}", "error")

    experiments_list = query("SELECT experimentId, name FROM experiment ORDER BY name")
    return render_template(
        "charge_form.html",
        experiments=experiments_list,
        preselect=str(ch["experimentId"]),
        record=ch,
    )


@app.route("/charges/<int:charge_id>/delete", methods=["POST"])
def charge_delete(charge_id):
    try:
        execute("DELETE FROM charge_adjustment WHERE chargeId = ?", (charge_id,))
        execute("DELETE FROM charge WHERE chargeId = ?", (charge_id,))
        flash("Charge removed.", "success")
    except sqlite3.IntegrityError as err:
        flash(f"Could not remove charge: {err}", "error")
    return redirect(url_for("charges"))


@app.route("/adjustments")
def adjustments():
    type_filter = request.args.get("type", "").strip()

    sql = """
        SELECT ca.adjustmentId, ca.adjustmentType, ca.amount, ca.adjustmentDate,
               c.chargeId, c.chargeType,
               e.experimentId, e.name AS experimentName
        FROM charge_adjustment ca
        JOIN charge c ON ca.chargeId = c.chargeId
        JOIN experiment e ON c.experimentId = e.experimentId
        WHERE 1=1
    """
    params = []
    if type_filter:
        sql += " AND ca.adjustmentType = ?"
        params.append(type_filter)
    sql += " ORDER BY ca.adjustmentDate DESC"

    rows = query(sql, tuple(params))
    types = [r["adjustmentType"] for r in query(
        "SELECT DISTINCT adjustmentType FROM charge_adjustment ORDER BY adjustmentType"
    )]
    total = sum(r["amount"] for r in rows)

    return render_template(
        "adjustments.html",
        adjustments=rows,
        types=types,
        type_filter=type_filter,
        total=total,
    )


@app.route("/adjustments/new", methods=["GET", "POST"])
def adjustment_new():
    if request.method == "POST":
        try:
            execute(
                """INSERT INTO charge_adjustment (chargeId, adjustmentType, amount, adjustmentDate)
                   VALUES (?, ?, ?, ?)""",
                (
                    int(request.form["charge_id"]),
                    request.form["adjustment_type"].strip(),
                    float(request.form["amount"]),
                    request.form["adjustment_date"].strip(),
                ),
            )
            flash("Adjustment added.", "success")
            return redirect(url_for("adjustments"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not add adjustment: {err}", "error")

    charges_list = query("""
        SELECT c.chargeId, c.chargeType, c.chargeAmount, e.name AS experimentName
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY c.chargeId
    """)
    return render_template("adjustment_form.html", charges=charges_list, record=None)


@app.route("/adjustments/<int:adj_id>/edit", methods=["GET", "POST"])
def adjustment_edit(adj_id):
    adj = query_one("SELECT * FROM charge_adjustment WHERE adjustmentId = ?", (adj_id,))
    if not adj:
        abort(404)
    if request.method == "POST":
        try:
            execute(
                """UPDATE charge_adjustment SET chargeId = ?, adjustmentType = ?, amount = ?, adjustmentDate = ?
                   WHERE adjustmentId = ?""",
                (
                    int(request.form["charge_id"]),
                    request.form["adjustment_type"].strip(),
                    float(request.form["amount"]),
                    request.form["adjustment_date"].strip(),
                    adj_id,
                ),
            )
            flash("Adjustment updated.", "success")
            return redirect(url_for("adjustments"))
        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not update adjustment: {err}", "error")

    charges_list = query("""
        SELECT c.chargeId, c.chargeType, c.chargeAmount, e.name AS experimentName
        FROM charge c
        JOIN experiment e ON c.experimentId = e.experimentId
        ORDER BY c.chargeId
    """)
    return render_template("adjustment_form.html", charges=charges_list, record=adj)


@app.route("/adjustments/<int:adj_id>/delete", methods=["POST"])
def adjustment_delete(adj_id):
    execute("DELETE FROM charge_adjustment WHERE adjustmentId = ?", (adj_id,))
    flash("Adjustment removed.", "success")
    return redirect(url_for("adjustments"))


@app.template_filter("money")
def money(value):
    """Format a number as $X,XXX.XX with sign."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    sign = "-" if v < 0 else ""
    return f"{sign}${abs(v):,.2f}"

@app.route("/equipment")
def equipment():

    exp_filter = request.args.get("experiment", "").strip()
    type_filter = request.args.get("type", "").strip()
    search = request.args.get("q", "").strip()

    sql = """

        SELECT
            ee.equipmentUsageId,
            ee.startDate,
            ee.endDate,

            e.experimentId,
            e.name AS experimentName,

            eq.equipmentName,
            eq.equipmentPurpose

        FROM experiment_equipment ee

        JOIN experiment e
            ON ee.experimentId = e.experimentId

        JOIN equipment eq
            ON ee.equipmentId = eq.equipmentId

        WHERE 1=1

    """

    params = []

    if exp_filter:
        sql += " AND e.experimentId = ?"
        params.append(exp_filter)

    if type_filter:
        sql += " AND eq.equipmentName = ?"
        params.append(type_filter)

    if search:
        sql += """
            AND (
                eq.equipmentName LIKE ?
                OR e.name LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    sql += " ORDER BY ee.startDate DESC"

    rows = query(sql, tuple(params))

    experiments_list = query("""
        SELECT experimentId, name
        FROM experiment
        ORDER BY name
    """)

    types = [
        r["equipmentName"]
        for r in query(
            "SELECT DISTINCT equipmentName FROM equipment ORDER BY equipmentName"
        )
    ]

    return render_template(
        "equipment.html",
        equipment=rows,
        experiments=experiments_list,
        types=types,
        exp_filter=exp_filter,
        type_filter=type_filter,
        search=search,
    )


@app.route("/facilities")
def facilities():

    exp_filter = request.args.get("experiment", "").strip()
    type_filter = request.args.get("type", "").strip()
    search = request.args.get("q", "").strip()

    sql = """

        SELECT
            ef.facilityUsageId,
            ef.startDate,
            ef.endDate,

            e.experimentId,
            e.name AS experimentName,

            f.facilityName,
            f.facilityType

        FROM experiment_facility ef

        JOIN experiment e
            ON ef.experimentId = e.experimentId

        JOIN facility f
            ON ef.facilityId = f.facilityId

        WHERE 1=1

    """

    params = []

    if exp_filter:
        sql += " AND e.experimentId = ?"
        params.append(exp_filter)

    if type_filter:
        sql += " AND f.facilityType = ?"
        params.append(type_filter)

    if search:
        sql += """
            AND (
                f.facilityName LIKE ?
                OR e.name LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    sql += " ORDER BY ef.startDate DESC"

    rows = query(sql, tuple(params))

    experiments_list = query("""
        SELECT experimentId, name
        FROM experiment
        ORDER BY name
    """)

    types = [
        r["facilityType"]
        for r in query(
            "SELECT DISTINCT facilityType FROM facility ORDER BY facilityType"
        )
    ]

    return render_template(
        "facilities.html",
        facilities=rows,
        experiments=experiments_list,
        types=types,
        exp_filter=exp_filter,
        type_filter=type_filter,
        search=search,
    )


@app.route("/equipment/new", methods=["GET", "POST"])
def equipment_new():

    if request.method == "POST":

        try:

            execute(
                """
                INSERT INTO experiment_equipment
                (experimentId, equipmentId, startDate, endDate)
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(request.form["experiment_id"]),
                    int(request.form["equipment_id"]),
                    request.form["start_date"].strip(),
                    request.form["end_date"].strip(),
                ),
            )

            flash("Equipment usage recorded.", "success")
            return redirect(url_for("equipment"))

        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not record equipment usage: {err}", "error")

    experiments_list = query("""
        SELECT experimentId, name
        FROM experiment
        ORDER BY name
    """)

    equipment_list = query("""
        SELECT equipmentId, equipmentName
        FROM equipment
        ORDER BY equipmentName
    """)

    return render_template(
        "equipment_form.html",
        experiments=experiments_list,
        equipment_list=equipment_list,
    )

@app.route("/facilities/new", methods=["GET", "POST"])
def facility_new():

    if request.method == "POST":

        try:

            execute(
                """
                INSERT INTO experiment_facility
                (
                    experimentId,
                    facilityId,
                    startDate,
                    endDate
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(request.form["experiment_id"]),
                    int(request.form["facility_id"]),
                    request.form["start_date"].strip(),
                    request.form["end_date"].strip(),
                ),
            )

            flash("Facility usage recorded.", "success")
            return redirect(url_for("facilities"))

        except (sqlite3.IntegrityError, ValueError, KeyError) as err:
            flash(f"Could not record facility usage: {err}", "error")

    experiments_list = query("""
        SELECT experimentId, name
        FROM experiment
        ORDER BY name
    """)

    facilities_list = query("""
        SELECT facilityId, facilityName, facilityType
        FROM facility
        ORDER BY facilityName
    """)

    return render_template(
        "facility_form.html",
        experiments=experiments_list,
        facilities_list=facilities_list,
    )
    
@app.route("/equipment/add", methods=["GET", "POST"])
def equipment_add():

    if request.method == "POST":

        equipment_name = request.form.get("equipment_name", "").strip()
        equipment_purpose = request.form.get("equipment_purpose", "").strip()
        sharing_status = request.form.get("sharing_status", "").strip()
        movability = request.form.get("movability", "").strip()
        hourly_rate = request.form.get("hourly_rate", "").strip()

        if not (
            equipment_name and
            equipment_purpose and
            sharing_status and
            movability and
            hourly_rate
        ):
            flash("All fields are required.", "error")

        else:
            try:

                execute(
                    """
                    INSERT INTO equipment
                    (
                        equipmentName,
                        equipmentPurpose,
                        sharingStatus,
                        movability,
                        hourlyRate
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        equipment_name,
                        equipment_purpose,
                        sharing_status,
                        movability,
                        int(hourly_rate),
                    ),
                )

                flash("Equipment added.", "success")
                return redirect(url_for("equipment"))

            except (sqlite3.IntegrityError, ValueError) as err:
                flash(f"Could not add equipment: {err}", "error")

    return render_template("equipment_add_form.html")

@app.route("/facilities/add", methods=["GET", "POST"])
def facility_add():

    if request.method == "POST":

        institution_id = request.form.get("institution_id", "").strip()
        facility_name = request.form.get("facility_name", "").strip()
        facility_type = request.form.get("facility_type", "").strip()
        term = request.form.get("term", "").strip()
        hourly_rate = request.form.get("hourly_rate", "").strip()

        if not (
            institution_id and
            facility_name and
            facility_type and
            term and
            hourly_rate
        ):
            flash("All fields are required.", "error")

        else:
            try:

                execute(
                    """
                    INSERT INTO facility
                    (
                        institutionId,
                        facilityName,
                        facilityType,
                        term,
                        hourlyRate
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        int(institution_id),
                        facility_name,
                        facility_type,
                        term,
                        int(hourly_rate),
                    ),
                )

                flash("Facility added.", "success")
                return redirect(url_for("facilities"))

            except (sqlite3.IntegrityError, ValueError) as err:
                flash(f"Could not add facility: {err}", "error")

    institutions = query("""
        SELECT institutionId, institutionName
        FROM institution
        ORDER BY institutionName
    """)

    return render_template(
        "facility_add_form.html",
        institutions=institutions
    )

@app.route("/equipment/list")
def equipment_list():

    search = request.args.get("q", "").strip()

    sql = """
        SELECT
            equipmentId,
            equipmentName,
            equipmentPurpose,
            sharingStatus,
            movability,
            hourlyRate
        FROM equipment
        WHERE 1=1
    """

    params = []

    if search:

        sql += """
            AND (
                equipmentName LIKE ?
                OR equipmentPurpose LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%"
        ])

    sql += " ORDER BY equipmentName"

    rows = query(sql, tuple(params))

    return render_template(
        "equipment_list.html",
        equipment=rows,
        search=search,
    )


@app.route("/facilities/list")
def facilities_list():

    search = request.args.get("q", "").strip()

    sql = """
        SELECT
            f.facilityId,
            f.facilityName,
            f.facilityType,
            f.term,
            f.hourlyRate,
            i.institutionName
        FROM facility f

        JOIN institution i
            ON f.institutionId = i.institutionId

        WHERE 1=1
    """

    params = []

    if search:

        sql += """
            AND (
                f.facilityName LIKE ?
                OR f.facilityType LIKE ?
                OR i.institutionName LIKE ?
            )
        """

        params.extend([
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ])

    sql += " ORDER BY f.facilityName"

    rows = query(sql, tuple(params))

    return render_template(
        "facilities_list.html",
        facilities=rows,
        search=search,
    )




if __name__ == "__main__":
    app.run(debug=True, port=5000)
