function val = validateValueAsPosScalar( val )

%by: Magnus Åberg

if ischar( val )
    val = str2double( val );
end
assert( ~isnan( val ), 'Value is not a scalar of type double' ) 
assert( isa( val, 'double' ), 'Value is not of type double.' )
assert( numel( val ) == 1 , 'Value is not scalar.' );
assert( val >= 0 ,'Value is not positive' )
end
