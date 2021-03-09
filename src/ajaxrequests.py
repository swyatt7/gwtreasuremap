# -*- coding: utf-8 -*-

import os, json, datetime
import random, math
import numpy as np
import healpy as hp
import astropy
import plotly
import plotly.graph_objects as go
import requests
import urllib.parse

from flask import Flask, request, jsonify
from flask_login import current_user
from sqlalchemy import func
from plotly.subplots import make_subplots
from plotly.tools import FigureFactory as FF

from . import function
from . import models
from . import forms
from . import enums
from src import app
from src import mail

db = models.db

#AJAX FUNCTIONS

@app.route('/ajax_scimma_xrt')
def ajax_scimma_xrt():
	args = request.args
	graceid = args['graceid']
	keywords = {
             'keyword':'',
             'cone_search':'',
             'polygon_search':'',
             'alert_timestamp_after':'',
             'alert_timestamp_before':'',
             'role':'',
             'event_trigger_number':graceid,
             'ordering':'',
             'page_size':1000,
    }
	base = 'http://skip.dev.hop.scimma.org/api/alerts/'
	url = '{}?{}'.format(base, urllib.parse.urlencode(keywords))
	r = requests.get(url)
	payload = []
	if r.status_code == 200:
		package = json.loads(r.text)['results']
		for p in package:
			payload.append(
				{
					'ra':p['right_ascension'],
					'dec':p['declination'],
					'info':function.sanatize_XRT_source_info(p)
				}
			)
	#print(payload)
	return jsonify(payload)

@app.route('/ajax_resend_verification_email')
def ajax_resend_verification_email():
	userid = current_user.id
	user = models.users.query.filter_by(id=userid).first()
	function.send_account_validation_email(user, notify=False)
	return jsonify('')


@app.route('/ajax_request_doi')
def ajax_request_doi():
	args = request.args
	graceid = args['graceid']
	graceid = models.gw_alert.alternatefromgraceid(graceid)
	if args['ids'] != '':
		ids = [int(x) for x in args['ids'].split(',')]

		points = db.session.query(
			models.pointing
		).filter(
			models.pointing_event.pointingid == models.pointing.id,
			models.pointing.id.in_(ids),
			models.pointing_event.graceid == graceid
		).all()

		user = db.session.query(models.users).filter(models.users.id == current_user.get_id()).first()

		if 'doi_group_id' in args: 
			valid, creators = models.doi_author.construct_creators(args['doi_group_id'], current_user.get_id())
			if not valid:
				creators = [{ 'name':str(user.firstname) + ' ' + str(user.lastname) }]
		else:
			creators = [{ 'name':str(user.firstname) + ' ' + str(user.lastname) }]


		insts = db.session.query(models.instrument).filter(models.instrument.id.in_([x.instrumentid for x in points]))
		inst_set = list(set([x.instrument_name for x in insts]))

		doi_url = args.get('doi_url')
		if doi_url:
			doi_id, doi_url = 0, doi_url
		else:
			doi_id, doi_url = function.create_pointing_doi(points, graceid, creators, inst_set)

		for p in points:
			p.doi_url = doi_url
			p.doi_id = doi_id

		db.session.commit()

		return jsonify(doi_url)


	return jsonify('')


@app.route("/coverage", methods=['GET','POST'])
def plot_prob_coverage():
	graceid = models.gw_alert.graceidfromalternate(request.args.get('graceid'))
	mappathinfo = request.args.get('mappathinfo')
	inst_cov = request.args.get('inst_cov')
	band_cov = request.args.get('band_cov')
	depth = request.args.get('depth_cov')
	depth_unit = request.args.get('depth_unit')

	if os.path.exists(mappathinfo):
		try:
			GWmap = hp.read_map(mappathinfo)
			#bestpixel = np.argmax(GWmap)
			nside = hp.npix2nside(len(GWmap))
		except:
			return '<b> Map ERROR. Please contact the administrator. <b>'
	else:
		return '<b>Calculator ERROR: Map not found. Please contact the administrator.</b>'

	pointing_filter = []
	pointing_filter.append(models.pointing_event.graceid == graceid)
	pointing_filter.append(models.pointing.status == 'completed')
	pointing_filter.append(models.pointing_event.pointingid == models.pointing.id)
	pointing_filter.append(models.pointing.instrumentid != 49)

	if inst_cov != '':
		insts_cov = [int(x) for x in inst_cov.split(',')]
		pointing_filter.append(models.pointing.instrumentid.in_(insts_cov))
	if band_cov != '':
		bands_cov = [x for x in band_cov.split(',')]
		pointing_filter.append(models.pointing.band.in_(bands_cov))
	if depth_unit != 'None' and depth_unit != '':
		pointing_filter.append(models.pointing.depth_unit == depth_unit)
	if depth != None and function.isFloat(depth):
		if 'mag' in depth_unit:
			pointing_filter.append(models.pointing.depth >= float(depth))
		elif 'flux' in depth_unit:
			pointing_filter.append(models.pointing.depth <= float(depth))
		else:
			return "You must specify a unit if you want to cut on depth."

	pointings_sorted = db.session.query(
		models.pointing.instrumentid,
		models.pointing.pos_angle,
		func.ST_AsText(models.pointing.position).label('position'),
		models.pointing.band,
		models.pointing.depth,
		models.pointing.time
	).filter(
		*pointing_filter
	).order_by(
		models.pointing.time.asc()
	).all()

	instrumentids = [x.instrumentid for x in pointings_sorted]
	#filter and query the relevant instrument footprints
	footprintinfo = db.session.query(
		func.ST_AsText(models.footprint_ccd.footprint).label('footprint'),
		models.footprint_ccd.instrumentid
	).filter(
		models.footprint_ccd.instrumentid.in_(instrumentids)
	).all()

	#get GW T0 time
	time_of_signal = db.session.query(
		models.gw_alert.time_of_signal
	).filter(
		models.gw_alert.graceid == graceid
	).filter(
		models.gw_alert.time_of_signal != None
	).order_by(
		models.gw_alert.datecreated.desc()
	).first()[0]

	if time_of_signal == None:
		return '<b>ERROR: Please contact administrator.</b>'

	qps = []
	qpsarea=[]
	times=[]
	probs=[]
	areas=[]
	NSIDE4area = 512 #this gives pixarea of 0.013 deg^2 per pixel
	pixarea = hp.nside2pixarea(NSIDE4area, degrees=True)

	for p in pointings_sorted:
		ra, dec = function.sanatize_pointing(p.position)

		footprint_ccds = [x.footprint for x in footprintinfo if x.instrumentid == p.instrumentid]
		sanatized_ccds = function.sanatize_footprint_ccds(footprint_ccds)
		for ccd in sanatized_ccds:
			pointing_footprint = function.project_footprint(ccd, ra, dec, p.pos_angle)


			ras_poly = [x[0] for x in pointing_footprint][:-1]
			decs_poly = [x[1] for x in pointing_footprint][:-1]
			xyzpoly = astropy.coordinates.spherical_to_cartesian(1, np.deg2rad(decs_poly), np.deg2rad(ras_poly))
			qp = hp.query_polygon(nside,np.array(xyzpoly).T)
			qps.extend(qp)


			#do a separate calc just for area coverage. hardcode NSIDE to be high enough so sampling error low
			qparea = hp.query_polygon(NSIDE4area, np.array(xyzpoly).T)
			qpsarea.extend(qparea)

			#deduplicate indices, so that pixels already covered are not double counted
			deduped_indices=list(dict.fromkeys(qps))
			deduped_indices_area = list(dict.fromkeys(qpsarea))

			area = pixarea * len(deduped_indices_area)

			prob = 0
			for ind in deduped_indices:
				prob += GWmap[ind]
			elapsed = p.time - time_of_signal
			elapsed = elapsed.total_seconds()/3600
			times.append(elapsed)
			probs.append(prob)
			areas.append(area)
			
	fig = make_subplots(specs=[[{"secondary_y": True}]])

	fig.add_trace(go.Scatter(x=times, y=[prob*100 for prob in probs],
						mode='lines',
						name='Probability'), secondary_y=False)
	fig.add_trace(go.Scatter(x=times, y=areas,
						mode='lines',
						name='Area'), secondary_y=True)
	fig.update_xaxes(title_text="Hours since GW T0")
	fig.update_yaxes(title_text="Percent of GW localization posterior covered", secondary_y=False)
	fig.update_yaxes(title_text="Area coverage (deg<sup>2</sup>)", secondary_y=True)
	coverage_div = plotly.offline.plot(fig,output_type='div',include_plotlyjs=False, show_link=False)

	return coverage_div


@app.route('/preview_footprint', methods=['GET'])
def preview_footprint():
	args = request.args

	form = forms.SubmitInstrumentForm(
		instrument_name = args.get('instrument_name'),
		instrument_type = args.get('instrument_type'),
		unit = args.get('unit'),
		footprint_type = args.get('footprint_type'),
		height = args.get('height'),
		width = args.get('width'),
		radius = args.get('radius'),
		polygon = args.get('polygon')
	)

	instrument = models.instrument()
	v = instrument.from_json(form, 0, True)

	if len(v[0].errors) == 0:
		trace = []
		vertices = v[2]
		print(vertices, 'vertices')
		for vert in vertices:
			xs = [v[0] for v in vert]
			ys =[v[1] for v in vert]
			trace1 = go.Scatter(
				x=xs,
				y=ys,
				line_color='blue',
				fill='tozeroy',
				fillcolor='violet'
			)
			trace.append(trace1)
		fig = go.Figure(data=trace)
		fig.update_layout(
			showlegend=False,
			xaxis_title = 'degrees',
			yaxis_title = 'degrees',
			yaxis=dict(
				matches='x',
				scaleanchor="x",
				scaleratio=1,
				constrain='domain',
			)
		)
		data = fig
		graphJSON = json.dumps(data, cls=plotly.utils.PlotlyJSONEncoder)
		return graphJSON
	print(v[0].errors)
	return jsonify("")


@app.route('/pointingfromid')
def get_pointing_fromID():
	args = request.args
	if 'id' in args and function.isInt(args.get('id')):
		#try:
		id = int(args.get('id'))
		pfilter = []
		pfilter.append(models.pointing.submitterid == current_user.get_id())
		pfilter.append(models.pointing.status == enums.pointing_status.planned)

		pointings = models.pointing.pointings_from_IDS([id], pfilter)

		if len(pointings) > 0:
			pointing = pointings[str(id)]

			pointing_json = {}

			position = pointing.position
			ra = position.split('POINT(')[1].split(' ')[0]
			dec = position.split('POINT(')[1].split(' ')[1].split(')')[0]

			pointing_json['ra'] = ra
			pointing_json['dec'] = dec
			pointing_json['graceid'] = pointing.graceid
			pointing_json['instrument'] = str(pointing.instrumentid)+'_'+enums.instrument_type(pointing.instrument_type).name
			pointing_json['band'] = pointing.band.name
			pointing_json['depth'] = pointing.depth
			pointing_json['depth_err'] = pointing.depth_err

			return jsonify(pointing_json)
		#except Exception as e:
		#	print(e)
		#	pass
	return jsonify('')

