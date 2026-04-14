function trackerData = nnFastTrack( raw, param )
%by: Magnus Åberg

%% parameters
mzLim = param.mzTolerance;
massStdAnchor = param.mzAnchor;
massTransformation = param.mzTransformation;

%% To make the mass uncertainty independent of the mass value (for
%% TOF-data)
switch massTransformation
    case 1 %sqrt
        mass_values = sqrt(raw.mass_values);
        mzLim=mzLim/sqrt(massStdAnchor);
    case 2 %none
        mass_values = raw.mass_values;
    otherwise
        error( [ mfilename, ': Unrecognised transformation "', massTransformation, '"' ] )
end

%% house keeping variables
nScans = numel( raw.scan_index );

%% allocate variables
id = ( 1 : numel( raw.mass_values ) )';
scan = zeros( size( id ) );
point = id;

%% initialization
pts0 = raw.scan_index( 1 ) + ( 1 : raw.point_count( 1 ) );
scan( pts0 ) = 1;
mz0 = mass_values( pts0 );

for i = 2 : nScans
    pts1 = raw.scan_index( i ) + ( 1 : raw.point_count( i ) );
    scan( pts1 ) = i;
    
    mz1 = mass_values( pts1 );
    
    matches = nnMatchWithBound( mz0, mz1, mzLim );
       
    p0 = pts0( matches( :, 1 ) );
    p1 = pts1( matches( :, 2 ) );
    id( p1 ) = id( p0 );

    mz1( matches( :, 2 ) ) = 0.5 * ( mz0( matches( :, 1 ) ) + mz1( matches( :, 2 ) ) ); % Approximate "Kalman filter" step
    mz0 = mz1;
    pts0 = pts1;
end


%% assign output
trackerData = [ id, point, scan ];