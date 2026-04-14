function [raw,included_points] = subsetRawData(raw,limits,mzLims)
% [raws] = subsetRawData(raw,limits)
%
% creates a subset of raw (LC/MS) data. limits(1:2) time in seconds,
% limits(3:4) m/z.

%by: Magnus Åberg
if ischar(raw)
   [raw,included_points] = subsetRawDataFromFile(raw,limits);
   return
end
if nargin>2
   limits = [limits(:)' mzLims(:)'];
end


included_time = raw.time_axis>=limits(1) & raw.time_axis <limits(2);

if ~any(included_time)
   raw.mass_values = [];
   raw.time_axis = [];
   raw.intensity_values = [];
   raw.points = [];
   raw.scan_index = [];
   raw.scan_id = [];
   raw.point_count = [];
   if isfield(raw,'precursor_mass')
      raw.precursor_mass = [];
   end

   included_points = [];
   return
end

start_time = find(included_time);
start_time = start_time(1);
stop_time = find(included_time);
stop_time = stop_time(end);

scan_index = [raw.scan_index; length(raw.mass_values)];
included_points = false(size(raw.mass_values));
included_points(scan_index(start_time)+1:scan_index(stop_time+1)) = true;

included_points = included_points & (raw.mass_values >=limits(3));
included_points = included_points & (raw.mass_values <= limits(4));

if sum(included_points) == numel(raw.mass_values)
   return
end

scan_index = zeros(sum(included_time),1);
k=0;
for i = 1:length(scan_index)-1,
   k = k + sum(included_points(raw.scan_index(start_time-1+i)+1:raw.scan_index(start_time+i)));
   scan_index(i+1)=k;
end

if ~isfield(raw,'points')
   raw.points = (1:numel(raw.mass_values))';
end
if ~isfield(raw,'scan_id')
   raw.scan_id = (1:numel(raw.scan_index))';
end

try
   raw.mass_values      = raw.mass_values(included_points);
   raw.intensity_values = raw.intensity_values(included_points);
   raw.points           = raw.points(included_points);
   raw.scan_index       = scan_index;
   raw.point_count      = diff([scan_index; numel(raw.mass_values)]); % added 2010-05-20 (bugfix) /MÅ
   raw.time_axis        = raw.time_axis(included_time);
   raw.scan_id          = raw.scan_id(included_time);
   raw.info.mass_range  = limits(3:4);

   if isfield(raw,'precursor_mass')
      raw.precursor_mass = raw.precursor_mass(included_points);
   end
   
   included_points = find(included_points);
catch
   disp(lasterr)
   keyboard
end