function raw=LoadMzML(File)
%Erik Tengstrand

fid = fopen( File, 'rt' );
assert( fid > 0, 'loadMzML: File "%s" could not be opened', File );  
c = char( fread( fid, inf, '*uchar' )' );
assert( fclose( fid ) == 0, 'loadMzML: error closing file "%s" with fid %i\n',File, fid );

%time
time = regexp( c,'name="scan start time" value="(?<value>\d+((\.|,)\d*){0,1})"','names');
time = regexprep( { time.value }, ',', '.');
time_axis = str2num(char( time ) );

unit = regexp( c,'unitName="(?<unit>Minutes|Seconds|Minute|Second|minutes|seconds|minute|second)"','names');
time_unit=lower(unit(1).unit);
switch time_unit
    case 'second'
        time_unit='seconds';
    case 'minute'
        time_unit='minutes';
end 
            

%mz and intensity data (binary)
expr='defaultArrayLength="(?<pointcount>\d+)".*?name="(?<mztype>32|64)-bit float.*?name="m/z array".*?<binary>(?<mz>[^<]+)</binary>.*?name="(?<inttype>32|64)-bit float.*?name="intensity array".*?<binary>(?<int>[^<]+)</binary>';
bin = regexp(c,expr,'names');

%preallocating
point_count=str2num( char(bin.pointcount));
scan_index=cumsum([0; point_count]);
mass_values=zeros(scan_index(end),1);
intensity_values=zeros(scan_index(end),1);

%converting mz and int binaries to actual values
for i=1:numel(bin)
    mz = decodeBase64( bin(i).mz, 'little', bin(i).mztype);
    int = decodeBase64( bin(i).int, 'little', bin(i).inttype);
    assert( numel( mz ) == numel( int ), 'LoadMzML: Mass and intensity vectors have different length - read error?');
    assert( numel( mz ) == point_count( i ), 'loadMzXMLData2: Mass vectors has length different from nominal - read error?' );
    mass_values(scan_index(i)+(1:point_count(i)))=mz;
    intensity_values(scan_index(i)+(1:point_count(i)))=int;
end

%creating the final struct
raw.time_axis = time_axis;
raw.mass_values = mass_values;
raw.intensity_values = intensity_values;
raw.point_count = point_count;
raw.scan_index = scan_index(1:(end-1));
raw.points=(1:numel(mass_values))';
raw.scan_id=(1:numel(time_axis))';
raw.info.unit=time_unit;