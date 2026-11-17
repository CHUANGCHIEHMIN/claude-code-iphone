#!/bin/sh
# Convert/normalise the sheets with ODA File Converter (https://www.opendesign.com/guestfiles/oda_file_converter)
# usage: oda_convert.sh <ODAFileConverter binary> <input dir with .dxf> <output dir>
# writes AutoCAD 2018 DWG (and, run again with DXF, an ODA-written AutoCAD 2018 DXF); audit enabled.
QT_QPA_PLATFORM=${QT_QPA_PLATFORM:-xcb} xvfb-run -a "$1" "$2" "$3" "ACAD2018" "DWG" "0" "1" "*.DXF"
