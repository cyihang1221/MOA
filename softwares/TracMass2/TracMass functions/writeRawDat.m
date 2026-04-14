function writeRawDat(pth,name,raw,overwrite)
% writeRawDat(pth,name,raw)
% write raw-data as pth\name.dat file so that it can be memory-mapped
% pth\name.mat contains time_axis, scan_index, point_count and ???
%
% Magnus Åberg, 2010-06-22
if ~exist('overwrite','var')
   overwrite = false;
end
   

a.datFile = fullfile(pth,[name,'.dat']);
matFile = fullfile(pth,[name,'.mat']);

if ~overwrite
   assert(isempty(dir(a.datFile)),sprintf('File: %s exists.',a.datFile));
end
X = [raw.mass_values,raw.intensity_values];

if ~exist( pth, 'dir' )
    mkdir( pth )
end

fid  = fopen(a.datFile,'w');
fwrite(fid,X,'double');
fid = fclose(fid);

assert(fid==0,'file problems.')

a.loadDat = sprintf('@(file)memmapfile(file,''format'',{''double'',[%i %i],''X''})',size(X));
a.comment = 'Use "m = loadDat(DAT_FILE)" to load the file by memory mapping.';
a.n = size(X,1);
a.time = raw.time_axis;
a.point_count = raw.point_count;
a.scan_index = raw.scan_index;
a.scan_id = raw.scan_id;
a.mass_range = minmax(raw.mass_values');
a.time_range = minmax(a.time(:)');
a.TIC = getTIC(raw);
a.BPC = getBPC(raw);
a.info=raw.info;
save(fullfile(pth,[name,'.mat']),'-struct','a')
