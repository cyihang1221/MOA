function varargout = plotRawData2(ax,raw,unit_of_time,time)
% [h] = plotRawData(raw)
% Plots raw LCMS data. 2D scatter plot --- time (x) vs. m/z (y)
%
% Magnus Åberg, 2005
% mgna@novonordisk.com
% Magnus Åberg, 2010, magnus.m.aberg@astrazeneca.com
time_unit = 's';
if nargin >1
   time_unit = unit_of_time;
end

h = plot(ax,getRawTime(raw)/time,raw.mass_values,'.');
set(h,'markersize',1);

xlabel(sprintf('time (%s)',time_unit))
ylabel('m/z')

axis tight
box on

if nargout>0
   varargout{1}=h;
end
