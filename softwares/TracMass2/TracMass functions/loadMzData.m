function [ raw ] = loadMzData( file )
%Magnus Åberg
%%
% disp( 'DEBUG!!!' )
% file = '\\sesodl-xp47399\maberdata\Jonas Bergström\Second GC-data 2011-08-24\Batch1\xml\Non1D3.mzdata.xml'

%% load raw data from mzXML format from Agilent QQQ

% open file
fid = fopen( file, 'rt' );
assert( fid > 0, 'loadMzData: File "%s" could not be opened', file );  
% read the whole file as char
c = char( fread( fid, inf, '*uchar' )' );

% close the file
assert( fclose( fid ) == 0, 'loadMzData: error closing file "%s" with fid %i\n', ...
    file, fid );
%% DEBUG
% disp(' DEBUG !!')
% if ~exist('C'), C = c; end
% c = C(1:1.02e5)
%% start reading data. Time of scans
%time = regexp( c, 'name="TimeIn(?<unit>Minutes|Seconds)"','names') %  OK.
time = regexp( c, 'name="TimeIn(?<unit>Minutes|Seconds)" value="(?<value>\d+((\.|,)\d*)*)"', 'names' );
unit = time(1).unit;
time = regexprep( { time.value }, ',', '.'); % exchange decimal comma for decimal point.

time_axis = str2num( strvcat( time ) );
if unit == 'Minutes',
    time_axis = time_axis * 60;
end
%% mass values
%expr = '<(\w+).*?>.*?</\1>'; % matches pars of XML tokens
%expr = '(?<value><mzArrayBinary>.*?</mzArrayBinary>)'; % ok.
%expr = '(?<value><mzArrayBinary>\s*<data.*?>.*?</data>\s*</mzArrayBinary>)'; % ok. but gives the same as expr above
%expr = '<mzArrayBinary>\s*(?<value><data.*?>.*?</data>)\s*</mzArrayBinary>'; % ok. better than above
%expr = '<mzArrayBinary>\s*<data.*?>(?<value>.*?<)/data>\s*</mzArrayBinary>'; % perfect. Validated!
expr = '<mzArrayBinary>\s*<data.*?>(?<value>.*?<)'; % perfect. Validated! - faster.

mass = regexp( c, expr, 'names' );

%% mass coding precision
expr = '<mzArrayBinary>\s*<data.*?precision="(?<value>\d{2})'; % ok.
massPrecision = regexp( c, expr, 'names', 'once' );

%% mass endianess
expr = '<mzArrayBinary>\s*<data.*?endian="(?<value>big|little)'; % ok.
massEndian = regexp( c, expr, 'names', 'once' );

%% mass scan length
expr = '<mzArrayBinary>\s*<data.*?length="(?<value>\d+)'; % ok.
pointCount = regexp( c, expr, 'names' );
pointCount = str2num( strvcat( pointCount.value ) );

%% intensity values
expr = '<intenArrayBinary>\s*<data.*?>(?<value>.*?<)'; 
inten = regexp( c, expr, 'names' );

%% intensity coding precision
expr = '<intenArrayBinary>\s*<data.*?precision="(?<value>\d{2})';  %ok.
intenPrecision = regexp( c, expr, 'names', 'once' );

%% intenstiy endianess
expr = '<intenArrayBinary>\s*<data.*?endian="(?<value>big|little)'; % ok.
intenEndian = regexp( c, expr, 'names', 'once' );

%% start processing intensty and mass values
N = sum( pointCount );
scanIndex = cumsum( [0; pointCount] );
M = zeros( N, 1);
I = zeros( N, 1);
for i = 1 : numel( mass )
    m = decodeBase64( mass( i ).value, massEndian.value, massPrecision.value );
    int = decodeBase64( inten( i ).value, intenEndian.value, intenPrecision.value );
    assert( numel( m ) == numel( int ), 'loadMzXMLData2: Mass and intensity vectors have different length - read error?');
    assert( numel( m ) == pointCount( i ), 'loadMzXMLData2: Mass vectors has length different from nominal - read error?' );
    I( scanIndex( i ) + ( 1 : pointCount( i ) ) ) = int;
    M( scanIndex( i ) + ( 1 : pointCount( i ) ) ) = m;
end


%% assign output

raw.time_axis = time_axis;
raw.mass_values = M;
raw.intensity_values = I;
raw.point_count = pointCount;
raw.scan_index = scanIndex(1:end-1);
raw.points = ( 1 : N )';
raw.scan_id = ( 1 : numel( raw.time_axis ) )';
raw.info.unit='seconds'; %time values are transformed if minutes