/*
Function to initialize the GWTM aladin interface
*/
function gwtmAladinInit(data) {
    var fov = 180;

    var aladinParams = {
        fov: fov, 
        target: data.target_init, 
        showGotoControl:true, 
        showFullscreenControl: true, 
        showSimbadPointerControl: true, 
        showShareControl: true, 
        realFullscreen: false, 
        cooFrame:"ICRSd", 
        showReticle: false
    };

    if ('aladin' in data){
        var aladin = data.aladin;
    }
    else {
        var aladin = A.aladin('#aladin-lite-div', aladinParams);
    }
    
    aladin_setImage(aladin, 'static/sun-logo-100.png', 'Sun at GW T0', data.sun_ra, data.sun_dec)
    aladin_setImage(aladin, 'static/moon-supersmall.png', 'Moon at GW T0', data.moon_ra, data.moon_dec)

    var detectionoverlaylist = aladin_setContours(aladin, data.detection_overlays)
    var instoverlaylist = aladin_setContours(aladin, data.inst_overlays)
    var grboverlaylist = aladin_setMOC(aladin, data.GRBoverlays)

    aladin_drawInstHTML(data.inst_overlays, 'alert_instruments_div')
    aladin_drawGRBHtml(data.GRBoverlays, 'alert_grbcov_div')

    var ret = {
        aladin: aladin,
        detectionoverlaylist: detectionoverlaylist,
        instoverlaylist: instoverlaylist,
        grboverlaylist: grboverlaylist
    }

    return ret;
};

$('input[name=survey]').change(function() {
    aladin.setImageSurvey($(this).val());
});

//sets an image into the initialized aladin instance
function aladin_setImage(
    aladin,
    imgsource,
    imgname,
    pos_ra, pos_dec
){
    var IMG = new Image();
    IMG.src = imgsource;
    var cat = A.catalog({shape: IMG, name: imgname})
    aladin.addCatalog(cat);
    cat.addSources(A.source(pos_ra, pos_dec))
};

/*
draws a MOC map on the aladin interface
returns the overlay list to memory so it can be remembered on event redraw
*/
function aladin_setMOC(
    aladin,
    moc_list
){
    moc_overlayList=[];
    for (i = 0; i < moc_list.length; i++) {
        var moc = A.MOCFromJSON(moc_list[i].json, {opacity: 0.25, color: moc_list[i].color, lineWidth: 1, name: moc_list[i].name});
        aladin.addMOC(moc);
        moc_overlayList[i] = moc;
        moc.hide()
    }
    return moc_overlayList
}

function aladin_setContours(
    aladin, 
    contour_list,
){
    overlaylist = [];
    for (i = 0; i < contour_list.length; i++) {
        var contour = A.graphicOverlay({id: i, color:contour_list[i].color, lineWidth: 2, name:contour_list[i].name});
        aladin.addOverlay(contour);
        var overlay_contours = contour_list[i].contours
        for (j = 0; j < overlay_contours.length; j++){
            contour.addFootprints([A.polygon(overlay_contours[j].polygon)])
        }
        overlaylist[i] = {
            'contour':contour,
            'toshow':true,
            'tocolor':contour_list[i].color
        }
    }
    return overlaylist
}

function aladin_setMarkers(
    aladin,
    marker_list
) {
    for (i = 0; i < marker_list.length; i++) {
    var groupname = marker_list[i].name
    var gal_markers = marker_list[i].markers
    var markerlayer = A.catalog({name:groupname})
    for (j = 0; j < gal_markers.length; j++) {
        var marker = A.marker(gal_markers[j].ra, gal_markers[j].dec, {popupTitle: gal_markers[j].name+"_gal", popupDesc: gal_markers[j].info})
        markerlayer.addSources([marker])
    }
    aladin.addCatalog(markerlayer)
    }
}

function aladin_sliderRedrawContours(
    aladin, 
    input_contour_list,
    set_contour_list,
    slidervals
) {
    mint = slidervals.mint
    maxt = slidervals.maxt

    for (i = 0; i < input_contour_list.length; i++) {
        var toshow = false
        var tocolor = ''
        var iter = 0
    
        for (j = 0; j < set_contour_list.length; j++) {
            if (input_contour_list[i].name == set_contour_list[j].contour.name) {
                toshow = set_contour_list[j].toshow; 
                tocolor = set_contour_list[j].tocolor; 
                iter = j
            }
        }
        
        var contour = A.graphicOverlay({id: i, color:tocolor, lineWidth: 2, name:input_contour_list[i].name});
        aladin.addOverlay(contour);
        var overlay_contours = input_contour_list[i].contours
        for (j = 0; j < overlay_contours.length; j++){
            if (overlay_contours[j].time >= mint && overlay_contours[j].time <= maxt){
                contour.addFootprints([A.polygon(overlay_contours[j].polygon)])
            }
            if (!toshow) { 
                contour.hide() 
            }
        }
        set_contour_list[iter].contour = contour
    }
    return set_contour_list
}

function aladin_removeContour(
    contouroverlaylist
) {
    for (i = 0; i < contouroverlaylist.length; i++) {
        contouroverlaylist[i].contour.removeAll()
    }
    aladin.view.requestRedraw();
}

/*
    Hides or shows an overlay from the checkbox
*/
function aladin_overlayToggle(
    target,
    overlay_list
) {
    var iter = 0
    for(var k=0; k<overlay_list.length; k++)
    {
        if (target.id == overlay_list[k].contour.name) {
            iter = k
        }
    }
    if (target.checked) {
        overlay_list[iter].contour.show()
        overlay_list[iter].toshow = true
    }
    else {
        overlay_list[iter].contour.hide()
        overlay_list[iter].toshow = false
    }
    aladin.view.requestRedraw();
}
/*
    Hides or shows the MOC from checkbox
*/
function aladin_mocToggle(
    target,
    moc_list
) {
    var iter = 0
    for(var k=0; k<moc_list.length; k++)
    {
        if (target.id == moc_list[k].name) {
        iter = k
        }
    }
    if (target.checked) {
        moc_list[iter].show()
    }
    else {
        moc_list[iter].hide()
    }
    aladin.view.requestRedraw();
}

/*
    Draws the html on the side of the aladin interface
    with the given html div-tid
*/
function aladin_drawInstHTML(
    overlay_list,
    div_name,
){
    var overlayhtml = '<form id="InstrumentSelector">';
    for (var k=0 ; k<overlay_list.length; k++) {
        var cat = overlay_list[k];
        //overlayhtml += '<fieldset><span class="indicator right-triangle"></span><label for="' + cat.name + '">';
        overlayhtml += '<fieldset><label for="' + cat.name + '">';
        overlayhtml += '<input id="' + cat.name + '" type="checkbox" value="' + cat.name + '" checked="checked"  >' + cat.name + '</input></label>';
        overlayhtml += '<div class="cat-options" style="display: none;"><table><tr><td>Color</td><td><input type="color"></input></td></tr></select></td></tr></table></div>';
        overlayhtml += '</fieldset>';
    }   
    overlayhtml += '</form>';
    $('#'+div_name).html(overlayhtml)
}

function aladin_drawGRBHtml(
    grboverlay_list,
    div_name
){
    var GRBhtml = '<form id="GRBInstrumentSelector">';
    for (var k=0 ; k<grboverlay_list.length; k++) {
        var cat = grboverlay_list[k];
        if (cat.name == 'Fermi in South Atlantic Anomaly'){
            GRBhtml += '<fieldset><label for="' + cat.name + '">' + cat.name + '</label>';
            GRBhtml += '</fieldset>';
        } else {
            GRBhtml += '<fieldset><label for="' + cat.name + '">';
            GRBhtml += '<input id="' + cat.name + '" type="checkbox" value="' + cat.name + '" >' + cat.name + '</input></label>';
            GRBhtml += '</fieldset>';
        }
    }
    GRBhtml += '</form>';
    $('#'+div_name).html(GRBhtml);
}

function aladin_setMarkerHtml(
    marker_list,
    marker_div,
) {
    var html = ''
    for (i = 0; i < marker_list.length; i++) {
    var groupname = marker_list[i].name
    html += '<button type="button" class="btn btn-primary btn-xs" data-toggle="collapse" data-target="#'+groupname+'">+</button>';
    html += '<p style="display: inline-block"> '+groupname+'</p>'
    html += '<div class="collapse" id="'+groupname+'">'
    var markers = marker_list[i].markers
    for (j = 0; j < markers.length; j++) {
        markername = markers[j].name
        html += '<fieldset ><label for="' + markername+ '">';
        html += '<input id="' + markername+ '" type="checkbox" value="' + markername + '" >' + markername + '</input></label>';
        html += '</fieldset>';
    } 
    html += '</div>'
    }
    $('#'+marker_div).html(html);
}

$('.indicator').click(function() {
    var $this = $(this);
    if ($this.hasClass('right-triangle')) {
        $this.removeClass('right-triangle');
        $this.addClass('down-triangle');
        $this.parent().find('.cat-options').slideDown(300);
        var hipsId = $(this).parent().find("input[type='checkbox']").val();
        var iter = 0
        for(var k=0; k<instoverlaylist.length; k++)
        {
          if (hipsId == instoverlaylist[k][0].name) {
            iter = k
          }
        }
        $this.parent().find("input[type='color']").val(instoverlaylist[iter][0].color);
    }
    else {
        $this.removeClass('down-triangle');
        $this.addClass('right-triangle');
        $this.parent().find('.cat-options').slideUp(300);
    }
});

/*
    Function that listens to the time slider. 
    clears the visualization and redraws the contours
    considers the time of the instrument pointings 
*/
$(function() {
    $( "#slider-range" ).slider({
        range: true,
        min: slider_min,
        max: slider_max,
        step: slider_step,
        values: slider_vals,

        slide: function( event, ui ) {
            slidervals = {
                mint : new Number(ui.values[0]),
                maxt : new Number(ui.values[1])
            }
            
            $("#amount").val((slidervals.mint).toFixed(3) + " - " + (slidervals.maxt).toFixed(3));
            aladin.removeLayers()
            
            aladin_setImage(aladin, 'static/sun-logo-100.png', 'Sun at GW T0', data.sun_ra, data.sun_dec)
            aladin_setImage(aladin, 'static/moon-supersmall.png', 'Moon at GW T0', data.moon_ra, data.moon_dec)
            detectionoverlaylist = aladin_setContours(aladin, data.detection_overlays)
            grboverlaylist = aladin_setMOC(aladin, data.GRBoverlays)
            instoverlaylist = aladin_sliderRedrawContours(aladin, data.inst_overlays, instoverlaylist, slidervals)
        }
  });
  $( "#amount" ).val( (new Number($( "#slider-range" ).slider( "values", 0 ))) +
    " - " + (new Number($( "#slider-range" ).slider( "values", 1 ))));
});