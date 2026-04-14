function time = getRawTime(raw)
%time = getRawTime(raw)
% get time-values for each data point
% Magnus Åberg 2010-06-22
% k.magnus.aberg@gmail.com
time = zeros(size(raw.mass_values));
for i = 1:length(raw.scan_index)-1,
   time(raw.scan_index(i)+1:raw.scan_index(i+1))=raw.time_axis(i);
end
time(raw.scan_index(end)+1:end) = raw.time_axis(end);

