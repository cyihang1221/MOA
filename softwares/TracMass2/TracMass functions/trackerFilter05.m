function [outList] = trackerFilter05(trackerList,raw,opts)
%[outList] = trackerFilter05(trackerList,raw,opts,REFX)
%    Removes trackers that are too short and has too low intensity. 
%    based on firm_track_filter_04
%    fix of the algorithm so that the trackerIDs need not be a compact set
%    on 1 to nTrackers.
%    
%  Magnus Åberg, 2010.

% constants
TRACKER_ID_COL = 1;
POINT_ID_COL = 2;
SCAN_ID_COL = 3;
time0 = cputime;

% default opts
tracker_min_length = 5;
tracker_min_intensity = 10;

if nargin > 2,
      tracker_min_length = opts.minLength;
      tracker_min_intensity = opts.minIntensity;
end

nPoints = size(trackerList,1);
if nPoints ==0,
   return
end
try
    trackerList  = sortrows(trackerList);
catch
    [trackerList(:,TRACKER_ID_COL), III] = sort(trackerList(:,TRACKER_ID_COL));
    
    trackerList(:,POINT_ID_COL) = trackerList(III,POINT_ID_COL);
    trackerList(:,SCAN_ID_COL ) = trackerList(III,SCAN_ID_COL );
end
    
% length OK?
[C,I,ref]=getCounts2(trackerList(:,TRACKER_ID_COL));
maskLen = C>=tracker_min_length;

map( ref ) = 1 : numel( ref );

% intensity OK?
maskKeep = raw.intensity_values( trackerList( :, POINT_ID_COL ) ) >= tracker_min_intensity;
maskIntens = false( size( maskLen ) );
maskIntens( map( unique( trackerList( maskKeep, 1 ) ) ) ) = true;

maskIDs = maskIntens & maskLen;

keepC = C( maskIDs );
keepI = I( maskIDs );
outList = zeros( sum( keepC ), 3 );
cnt = 0;

for i = 1 : numel( keepC )
    p = ( 1 : keepC( i ) );
    pts  = cnt + p;
    cnt  = cnt + keepC( i );
    pts0 = keepI( i ) + p;
    outList( pts, : ) = trackerList( pts0, : );
end

%[foo,III] = sort(outList(:,1)+outList(:,2)/(2*max(outList(:,2))));
%for i = 1:3,
%    outList(:,i) = outList(III,i);
%end

%(1,'Tracker filter: Execution time = %s\n',sprintf_time(cputime-time0));
