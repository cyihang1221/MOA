function raw=LoadRawDataV3(File,ProjectPath)
%arguments:File
%loads raw data and save a .dat file. If a .dat file exists, it will load
%the .dat file instead (for speed).

%by: Erik Tengstrand
File=char(File);
[Path,Name,Extension]=fileparts(File);

if nargin==2
    rawDatFile = fullfile( ProjectPath,'raw-dat', [ Name, '.dat' ] );
    
    if exist( rawDatFile, 'file' ) == 2,
        raw=DatFile([ProjectPath filesep 'raw-dat'],Name,rawDatFile);
        return
    end
end

switch lower(Extension)
    case '.cdf'
        raw=CdfFile(File);
    case '.dat'
        raw=DatFile(Path,Name,File);
        return
    case {'.mzdata' ,'.xml'}
        raw = loadMzData(File);
    case '.mzxml'
        raw=loadMzXML(File); 
    case {'.man' ,'.mzml'}
        raw=LoadMzML(File);
end

%if there is no .dat file, it will be written here.
if nargin==2
if isdir(ProjectPath)
    writeRawDat([ProjectPath filesep 'raw-dat'],Name,raw,false );
end
end


    function raw=DatFile(Path,Name,rawDatFile)
        matFile = fullfile( Path, [ Name, '.mat' ] );
        assert( exist( matFile, 'file' ) == 2 )
        raw = load( matFile );
        
        fid = fopen( rawDatFile, 'r' );
        assert( fid > 0 ); 
        data = fread( fid, inf, '*double' );
        assert( fclose( fid ) == 0 );  
        
        raw.mass_values = data(1: numel(data) / 2);
        raw.intensity_values = data( ( numel(data) / 2 + 1) : end ) ;
        raw.time_axis = raw.time;
        raw.points  = 1 : numel( raw.mass_values );
        raw.scan_id = 1 : numel( raw.time_axis );
        raw = rmfield( raw, 'time' );
    end


    function raw=CdfFile(File)
        assert( exist( File, 'file' ) == 2 , 'loadRawData: File not found')
        
        raw.mass_values = nc_varget(File,'mass_values');
        raw.intensity_values = nc_varget(File,'intensity_values');
        raw.points = (1:numel(raw.mass_values))';
        raw.scan_index = nc_varget(File,'scan_index');
        raw.time_axis = nc_varget(File,'scan_acquisition_time');
        raw.scan_id = (1:numel(raw.scan_index))';
        raw.point_count = diff( [raw.scan_index ; numel(raw.mass_values)] );
        
        raw.info.File = File;
        try
            raw.info.unit=lower(nc_attget(File,nc_global,'units'));
        catch
            raw.info.unit='seconds';
        end
        
        try
            raw.info.mass_range = [nc_attget(File,nc_global,'global_mass_min') ...
                nc_attget(File,nc_global,'global_mass_max')];
        catch
            raw.info.mass_range = [ floor( min( raw.mass_values ) ), ceil( max( raw.mass_values ) ) ];
        end
        raw.info.intensity_threshold = 0;
    end

end