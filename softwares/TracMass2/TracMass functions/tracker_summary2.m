function [ts] = tracker_summary2(trackerList,raw)
%[ts] = tracker_summary2(trackerList,raw)
%
%  TRACKER_SUMMARY2 computes an intensity weighted m/z value for each
%  tracker and assigns the tracker with start and stop times.

%by: Magnus Åberg

ts.ID = unique(trackerList(:,1)); % ts.ID is sorted in ascending order.
trackerList = sortrows( trackerList );
[ counts, indStart, ts.ID ] = getCounts2( trackerList( :, 1 ) );
nTrackers = numel( ts.ID ); 

ts.mz = zeros( nTrackers, 1 );
ts.timeStart = raw.time_axis( trackerList(indStart + 1, 3 ) );
ts.timeStop = raw.time_axis( trackerList(indStart + counts, 3 ) );
ts.intensity = zeros( nTrackers, 1 );
ts.time = zeros( nTrackers,1);

for iTrack = 1:nTrackers,
   inds = indStart( iTrack ) + ( 1 : counts( iTrack ) );
   points = trackerList( inds, 2 );
   scans  = trackerList( inds, 3 );
   
   intensities = raw.intensity_values( points );
   masses = raw.mass_values( points );
   [ intensityMax, tmpInd ] = max( intensities );
   weights = intensities;
   weights = weights / sum( intensities ); % normalize to unit sum
   ts.mz( iTrack ) = sum( masses .* weights );

   ts.intensity( iTrack ) = intensityMax;
   ts.time( iTrack )                  = raw.time_axis( scans( tmpInd ) );
   
end