function [ matches] =  nnMatchWithBound( x, y, lim )
%by: Magnus Åberg
%%
xyi = [ x(:), ( 1 : numel( x ) )'; ...
    y(:), -( 1 : numel( y ) )' ];

xyi = sortrows( xyi );

d = diff( [ xyi(:,1); inf ] ) ;
s = [sign( xyi( 2 : end, 2 ).* xyi( 1 : end - 1, 2 ) ); 0 ];

tf = d < lim & s < 0;

%% Greedy assignment - smallest difference first
score = double( tf ) + [0; double( tf( 1 : end - 1 ) ) ]; 

inds = find( score > 1 );
[ dmin, ii ] =  min( [ d( inds )  d(inds - 1 ) ], [], 2 );

dmi = sortrows( [ dmin ii inds] );
for i = 1 : numel( inds )
    theInd = dmi( i, 3 ) + 1 - dmi( i, 2 );
    altInd = dmi( i, 3 ) - 2 + dmi( i, 2 ); 
    if tf( theInd ) % may have been set false in earlier iteration
        tf( altInd ) = false;
    end
end

matches = [xyi( tf, 2 ) xyi( [ false; tf( 1 : end - 1 ) ], 2 ) ];
matches = sort( -matches, 2 );
matches = abs( matches );

n = size( matches, 1 );
assert( numel( unique( matches( :, 1 ) ) ) == n, 'Error. Ambigous match in x.' )
assert( numel( unique( matches( :, 2 ) ) ) == n, 'Error. Ambigous match in y.' )