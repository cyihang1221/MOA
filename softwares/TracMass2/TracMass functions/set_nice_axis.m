function [] = set_nice_axis(varargin)
%by: Magnus Åberg

if nargin ==1,
    figure(varargin{1})
end
framePercent = 0.05;
if nargin>0 && mod(nargin,2)==0,
   varList = {'framePercent'};
   assign_varargin_options(varList,varargin);
end
axis tight

ax = axis;
if framePercent >= .5
   framePercent = framePercent/100;
end

xrange = ax(2) - ax(1);
yrange = ax(4) - ax(3);

ax(1) = ax(1) - framePercent*xrange;
ax(2) = ax(2) + framePercent*xrange;
ax(3) = ax(3) - framePercent*yrange;
ax(4) = ax(4) + framePercent*yrange;

axis(ax)
