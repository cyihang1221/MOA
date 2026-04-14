function raw = loadMzXML( file )
%Magnus Åberg

%% open file
fid = fopen( file, 'rt' );
assert( fid > 0, 'loadMzXML: File "%s" could not be opened', file );  
% read the whole file as char
c = char( fread( fid, inf, '*uchar' )' );

% close the file
assert( fclose( fid ) == 0, 'loadMzXMLData2: error closing file "%s" with fid %i\n', ...
    file, fid );
%% read data
result = regexp( c, 'scan num="(?<scan>\d+)"','names');
scan = str2num( strvcat( result.scan ) );

result = regexp( c, 'peaksCount="(?<pointCount>\d+)"','names');
pointCount = str2num( strvcat( result.pointCount ) );

%%
result = regexp( c, 'retentionTime="\D+(?<time>\d+(\.\d*){0,1})(?<unit>\w+)"','names');

time_axis = str2num( strvcat( result.time )  );
timeUnit = result(1).unit;

%%
result = regexp( c, 'totIonCurrent="(?<tic>\d+(\.\d*){0,1})"','names');
TIC = str2num( strvcat( result.tic ) );

%% Byte order
result = regexp( c, 'byteOrder="(?<byteOrder>\w+)"','names','once');
byteOrder = result.byteOrder;

%% precision
result = regexp( c, 'precision="(?<precision>\d+)"','names','once');
precision = result.precision;

%% pair order
result = regexp( c, 'pairOrder="(?<order>[^"]+)"','names','once' );
pairOrder = result.order;

%% mz-spectra
result = regexp( c, '<peaks [^>]+>(?<data>[^<]+)</peaks>','names');

%% decode spectra
N = sum( pointCount );
scanIndex = cumsum( [0; pointCount] );
M = zeros( N, 1);
I = zeros( N, 1);

for i = 1 : numel( result )
    data = decodeBase64( result( i ).data, byteOrder, precision );
    mz = data( 1:2:end );
    int = data( 2:2:end );
    assert( numel( mz ) == numel( int ), 'loadMzXML: mass and intensity vectors have different lengths.')
    assert( numel( mz ) == pointCount( i ), 'loadMzXML: Mass vectors has length different from nominal - read error?' );
    I( scanIndex( i ) + ( 1 : pointCount( i ) ) ) = int;
    M( scanIndex( i ) + ( 1 : pointCount( i ) ) ) = mz;
end

switch lower(pairOrder)
    case 'm/z-int'
        % do nothing
    case 'int-m/z' % switch intensity and m/z vectors
        tmp = I;
        I = M;
        M = tmp;
    otherwise
        error( 'loadMzXML: unknown pair order.' )
end
        

%% assign output
raw.time_axis = time_axis;
raw.mass_values = M;
raw.intensity_values = I;
raw.point_count = pointCount;
raw.scan_index = scanIndex(1:end-1);
raw.points = ( 1 : N )';
raw.scan_id = ( 1 : numel( raw.time_axis ) )';
if timeUnit=='S'
    raw.info.unit='seconds';
else
    raw.info.unit='minutes';
end