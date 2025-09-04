from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from math import ceil
import random

app = Flask(__name__)
app.secret_key = "dragonboatsecret"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///teams.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Create tables immediately
with app.app_context():
    db.create_all()

# Models
class Team(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    category = db.Column(db.String(100), nullable=False)

class Heat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    heat_number = db.Column(db.Integer, nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    heat_id = db.Column(db.Integer, db.ForeignKey('heat.id'), nullable=False)
    lane = db.Column(db.Integer, nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)

# Home page -> Agencies/Groups summary
@app.route('/')
def home():
    teams = Team.query.all()
    agency_dict = {}
    for t in teams:
        if t.department not in agency_dict:
            agency_dict[t.department] = set()
        agency_dict[t.department].add(t.category)
    agencies_list = []
    for dept, cats in agency_dict.items():
        agencies_list.append({'department': dept, 'categories': sorted(list(cats)), 'count': len(cats)})
    agencies_list.sort(key=lambda x: x['department'])
    return render_template('agencies.html', agencies=agencies_list, teams=teams)

# Teams page
@app.route('/teams')
def index():
    teams = Team.query.all()
    return render_template('index.html', teams=teams)

# Add Team
@app.route('/add', methods=['GET', 'POST'])
def add_team():
    if request.method == 'POST':
        name = request.form['name']
        department = request.form['department']
        category = request.form['category']
        team = Team(name=name, department=department, category=category)
        db.session.add(team)
        db.session.commit()
        flash(f'Team {name} added!', 'success')
        return redirect(url_for('index'))
    return render_template('add_team.html')

# Delete single team
@app.route('/delete_team/<int:team_id>', methods=['POST'])
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash(f'Team {team.name} deleted.', 'warning')
    return redirect(url_for('index'))

# Reset all teams and heats
@app.route('/reset_all', methods=['POST'])
def reset_all():
    Assignment.query.delete()
    Heat.query.delete()
    Team.query.delete()
    db.session.commit()
    flash('All teams and heats cleared!', 'warning')
    return redirect(url_for('index'))

# Lane draw overview
@app.route('/lane_draw')
def lane_draw():
    teams = Team.query.all()
    categories = sorted(set([t.category for t in teams]))
    return render_template('lane_draw.html', categories=categories, teams=teams)

# Category lane draw
@app.route('/lane_draw/<category>', methods=['GET', 'POST'])
def category_draw(category):
    teams = Team.query.filter_by(category=category).all()
    heats = Heat.query.filter_by(category=category).order_by(Heat.heat_number).all()
    drawn = len(heats) > 0

    if request.method == 'POST':
        # Clear existing heats and assignments
        for heat in heats:
            Assignment.query.filter_by(heat_id=heat.id).delete()
        Heat.query.filter_by(category=category).delete()
        db.session.commit()

        # Shuffle teams for randomness
        team_list = teams[:]
        random.shuffle(team_list)
        num_teams = len(team_list)

        if num_teams <= 6:
            # Single heat
            heat = Heat(category=category, heat_number=1)
            db.session.add(heat)
            db.session.commit()
            start_lane = 1 if num_teams == 6 else 2
            for idx, team in enumerate(team_list):
                assignment = Assignment(heat_id=heat.id, lane=start_lane + idx, team_id=team.id)
                db.session.add(assignment)
        else:
            # Split into 2 heats
            num_heats = 2
            base_teams_per_heat = num_teams // num_heats
            extra = num_teams % num_heats
            idx = 0

            for i in range(num_heats):
                teams_in_this_heat = base_teams_per_heat + (1 if i < extra else 0)
                heat = Heat(category=category, heat_number=i+1)
                db.session.add(heat)
                db.session.commit()
                start_lane = 1 if teams_in_this_heat == 6 else 2
                for lane_offset in range(teams_in_this_heat):
                    assignment = Assignment(
                        heat_id=heat.id,
                        lane=start_lane + lane_offset,
                        team_id=team_list[idx].id
                    )
                    db.session.add(assignment)
                    idx += 1

        db.session.commit()
        flash(f'Lane draw completed for {category}.', 'success')
        return redirect(url_for('category_draw', category=category))

    # Prepare heats for display with 6 lanes each
    heat_data = []
    for heat in heats:
        assignments = Assignment.query.filter_by(heat_id=heat.id).order_by(Assignment.lane).all()
        rows = []
        lane_dict = {a.lane: a.team_id for a in assignments}
        for lane in range(1, 7):
            if lane in lane_dict:
                team_obj = Team.query.get(lane_dict[lane])
                rows.append({'lane': lane, 'team': team_obj.name, 'department': team_obj.department})
            else:
                rows.append({'lane': lane, 'team': '-', 'department': '-'})
        heat_data.append({'heat_number': heat.heat_number, 'rows': rows})

    return render_template('category_draw.html', category=category, teams=teams, heats=heat_data, drawn=drawn)

# Re-draw lanes
@app.route('/lane_draw/<category>/redraw', methods=['POST'])
def category_redraw(category):
    heats = Heat.query.filter_by(category=category).all()
    for heat in heats:
        Assignment.query.filter_by(heat_id=heat.id).delete()
    Heat.query.filter_by(category=category).delete()
    db.session.commit()
    flash('Previous lane draw cleared. Perform a new draw now.', 'warning')
    return redirect(url_for('category_draw', category=category))

# Agencies/Groups summary
@app.route('/agencies')
def agencies():
    teams = Team.query.all()
    agency_dict = {}
    for t in teams:
        if t.department not in agency_dict:
            agency_dict[t.department] = set()
        agency_dict[t.department].add(t.category)
    agencies_list = []
    for dept, cats in agency_dict.items():
        agencies_list.append({'department': dept, 'categories': sorted(list(cats)), 'count': len(cats)})
    agencies_list.sort(key=lambda x: x['department'])
    return render_template('agencies.html', agencies=agencies_list, teams=teams)

if __name__ == '__main__':
    app.run(debug=True)
