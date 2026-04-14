function tic = getTIC(raw)
%Magnus Åberg
scan_index = raw.scan_index;
scan_index(end+1) = numel(raw.intensity_values);

tic = zeros(size(raw.time_axis));
for i = 1:numel(raw.time_axis)
   tic(i) = sum(raw.intensity_values(scan_index(i)+1:scan_index(i+1)));
end

   